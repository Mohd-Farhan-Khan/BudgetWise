from app import app, Transaction, User
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# Import ML libraries
from sklearn.preprocessing import MinMaxScaler
import joblib

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
    HAS_TENSORFLOW = True
except ImportError:
    print("❌ TensorFlow not installed!")
    HAS_TENSORFLOW = False

def create_sequences(data, sequence_length):
    """Create sequences for LSTM training"""
    sequences = []
    targets = []
    
    for i in range(len(data) - sequence_length):
        seq = data[i:(i + sequence_length)]
        target = data[i + sequence_length]
        sequences.append(seq)
        targets.append(target)
    
    return np.array(sequences), np.array(targets)

def prepare_training_data(df):
    """Prepare data for LSTM training"""
    # Convert date column to datetime
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Create daily spending aggregation
    daily_spending = df.groupby('date')['amount'].sum().reset_index()
    
    # Fill missing dates with 0 spending
    date_range = pd.date_range(
        start=daily_spending['date'].min(),
        end=daily_spending['date'].max(),
        freq='D'
    )
    
    full_range = pd.DataFrame({'date': date_range})
    daily_spending = full_range.merge(daily_spending, on='date', how='left')
    daily_spending['amount'] = daily_spending['amount'].fillna(0)
    
    return daily_spending

def train_lstm_model():
    """Train LSTM model with correct parameters"""
    if not HAS_TENSORFLOW:
        print("❌ TensorFlow not available. Cannot train LSTM model.")
        return False
    
    with app.app_context():
        # Get first user
        user = User.query.first()
        if not user:
            print("❌ No users found!")
            return False
        
        print(f"🚀 Training LSTM model for user: {user.username}")
        
        # Get all expense transactions
        transactions = Transaction.query.filter_by(
            user_id=user.id,
            transaction_type='expense'
        ).order_by(Transaction.date.asc()).all()
        
        if len(transactions) < 50:
            print(f"❌ Not enough data. Need at least 50 transactions, have {len(transactions)}")
            return False
        
        print(f"📊 Found {len(transactions)} expense transactions")
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            'date': t.date,
            'amount': float(t.amount)
        } for t in transactions])
        
        print(f"📅 Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"💰 Total spending: ₹{df['amount'].sum():,.2f}")
        print(f"📈 Average daily: ₹{df['amount'].mean():.2f}")
        
        # Prepare daily data
        daily_data = prepare_training_data(df)
        print(f"📊 Prepared {len(daily_data)} days of data")
        
        if len(daily_data) < 30:
            print("❌ Not enough daily data for training")
            return False
        
        # Prepare data for LSTM
        amounts = daily_data['amount'].values.reshape(-1, 1)
        
        # Scale the data
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = scaler.fit_transform(amounts)
        
        # Create sequences (using 7 days to predict next day)
        sequence_length = 7
        X, y = create_sequences(scaled_data.flatten(), sequence_length)
        
        if len(X) < 20:
            print(f"❌ Not enough sequences for training. Need at least 20, have {len(X)}")
            return False
        
        print(f"📊 Created {len(X)} sequences of length {sequence_length}")
        
        # Split data (80% train, 20% test)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Reshape for LSTM [samples, time steps, features]
        X_train = X_train.reshape((X_train.shape[0], X_train.shape[1], 1))
        X_test = X_test.reshape((X_test.shape[0], X_test.shape[1], 1))
        
        print(f"📊 Training data shape: {X_train.shape}")
        print(f"📊 Test data shape: {X_test.shape}")
        
        # Build LSTM model
        model = Sequential([
            LSTM(50, return_sequences=True, input_shape=(sequence_length, 1)),
            Dropout(0.2),
            LSTM(50, return_sequences=True),
            Dropout(0.2),
            LSTM(50, return_sequences=False),
            Dropout(0.2),
            Dense(25, activation='relu'),
            Dense(1)
        ])
        
        # Compile model
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        print("🏗️ Model architecture:")
        model.summary()
        
        # Early stopping to prevent overfitting
        early_stopping = EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        # Train model
        print("🚀 Starting training...")
        history = model.fit(
            X_train, y_train,
            batch_size=16,
            epochs=100,
            validation_data=(X_test, y_test),
            callbacks=[early_stopping],
            verbose=1
        )
        
        # Evaluate model
        train_loss = model.evaluate(X_train, y_train, verbose=0)
        test_loss = model.evaluate(X_test, y_test, verbose=0)
        
        print(f"\n📊 Training Results:")
        print(f"   Training Loss: {train_loss[0]:.6f}")
        print(f"   Test Loss: {test_loss[0]:.6f}")
        print(f"   Training MAE: {train_loss[1]:.6f}")
        print(f"   Test MAE: {test_loss[1]:.6f}")
        
        # Save model and scaler
        os.makedirs('models', exist_ok=True)
        
        model_path = 'models/lstm_model.h5'
        scaler_path = 'models/lstm_model_scaler.pkl'
        
        model.save(model_path)
        joblib.dump(scaler, scaler_path)
        
        print(f"✅ Model saved to: {model_path}")
        print(f"✅ Scaler saved to: {scaler_path}")
        
        # Test prediction
        print("\n🧪 Testing prediction...")
        test_sequence = scaled_data[-sequence_length:].reshape(1, sequence_length, 1)
        prediction = model.predict(test_sequence, verbose=0)
        prediction_unscaled = scaler.inverse_transform(prediction)[0, 0]
        
        recent_avg = np.mean(amounts[-7:])
        print(f"   Recent 7-day average: ₹{recent_avg:.2f}")
        print(f"   Model prediction for next day: ₹{prediction_unscaled:.2f}")
        
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 LSTM MODEL TRAINER")
    print("=" * 60)
    
    success = train_lstm_model()
    
    if success:
        print("\n✅ LSTM model training completed successfully!")
        print("🎯 You can now use LSTM predictions in your app")
    else:
        print("\n❌ LSTM model training failed!")
        print("📊 The app will fall back to statistical predictions")
    
    print("=" * 60)