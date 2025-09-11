const API_BASE = "http://127.0.0.1:5001"; // updated port

// Check authentication
function checkAuth() {
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = 'login.html';
    return false;
  }
  return true;
}

// Get authenticated user details
function getUser() {
  return {
    id: localStorage.getItem('user_id'),
    username: localStorage.getItem('username'),
    email: localStorage.getItem('email')
  };
}

// Logout function
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('username');
  localStorage.removeItem('email');
  window.location.href = 'login.html';
}

// Add event listener to expense form
document.getElementById("expenseForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  
  if (!checkAuth()) return;
  
  const date = document.getElementById("date").value;
  const category = document.getElementById("category").value;
  const note = document.getElementById("note").value;
  const amount = parseFloat(document.getElementById("amount").value);
  const type = document.getElementById("type").value;

  try {
    const res = await fetch(`${API_BASE}/add_expense`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ date, category, note, amount, type })
    });
    
    if (res.status === 401) {
      alert("Your session has expired. Please login again.");
      logout();
      return;
    }
    
    // Attempt to parse JSON if possible
    let payloadText = null;
    let data = null;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      try { data = await res.json(); } catch (_) {}
    } else {
      payloadText = await res.text();
    }

    if (!res.ok) {
      const msg = (data && (data.message || data.error || data.msg)) || payloadText || `Request failed (${res.status})`;
      alert(`Failed to add transaction: ${msg}`);
      if (res.status === 422 && /Subject must be a string/i.test(msg)) {
        // Old token generated before fix; force re-login
        logout();
        return;
      }
      return; // Don't reload expenses on failure
    }

    alert((data && (data.message || data.msg)) || "Transaction added successfully");
    loadExpenses();
  } catch (err) {
    console.error("Error adding expense:", err);
    alert("Failed to add transaction. Please try again.");
  }
});

// Load expenses for the authenticated user
async function loadExpenses() {
  if (!checkAuth()) return;
  
  try {
    const res = await fetch(`${API_BASE}/expenses`, {
      headers: {
        "Authorization": `Bearer ${localStorage.getItem('token')}`
      }
    });
    
    if (res.status === 401) {
      alert("Your session has expired. Please login again.");
      logout();
      return;
    }
    
    if (!res.ok) {
      let errMsg = "Unable to load expenses";
      try {
        const errData = await res.json();
        errMsg = errData.message || errData.error || errData.msg || errMsg;
      } catch (_) {}
      if (res.status === 422 && /Subject must be a string/i.test(errMsg)) {
        alert('Session is invalid (token format). Please login again.');
        logout();
        return;
      }
      document.getElementById("expenseList").innerHTML = `<li>${errMsg}</li>`;
      return;
    }

    const expenses = await res.json();
    const list = document.getElementById("expenseList");
    list.innerHTML = "";
    
    if (expenses.length === 0) {
      list.innerHTML = "<li>No expenses found. Add your first expense!</li>";
      document.getElementById("total").textContent = "$0.00";
      return;
    }
    
    let totalExpense = 0;
    let totalIncome = 0;
    
    expenses.forEach(exp => {
      const li = document.createElement("li");
      const formattedDate = new Date(exp.date).toLocaleDateString();
      
      if (exp.type === 'Income') {
        totalIncome += parseFloat(exp.amount);
        li.className = 'income';
      } else {
        totalExpense += parseFloat(exp.amount);
        li.className = 'expense';
      }
      
      li.innerHTML = `
        <span class="date">${formattedDate}</span>
        <span class="category">${exp.category || 'Uncategorized'}</span>
        <span class="amount">${exp.type === 'Income' ? '+' : '-'}$${parseFloat(exp.amount).toFixed(2)}</span>
        ${exp.note ? `<span class="note">${exp.note}</span>` : ''}
      `;
      list.appendChild(li);
    });
    
    // Update summary
    document.getElementById("total-expense").textContent = `$${totalExpense.toFixed(2)}`;
    document.getElementById("total-income").textContent = `$${totalIncome.toFixed(2)}`;
    document.getElementById("balance").textContent = `$${(totalIncome - totalExpense).toFixed(2)}`;
  } catch (err) {
    console.error("Error loading expenses:", err);
    document.getElementById("expenseList").innerHTML = "<li>Error loading expenses. Please try again.</li>";
  }
}

// Setup user info in the dashboard
function setupUserInfo() {
  if (!checkAuth()) return;
  
  const user = getUser();
  document.getElementById("username-display").textContent = user.username;
  document.getElementById("logout-btn").addEventListener("click", logout);
}

// Initialize dashboard
window.addEventListener('load', () => {
  setupUserInfo();
  loadExpenses();
  
  // Set default date to today
  const today = new Date().toISOString().split('T')[0];
  document.getElementById("date").value = today;
});
