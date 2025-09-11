const API_BASE = "http://127.0.0.1:5001"; // updated port

// Chart objects to access globally
let incomeExpenseChart = null;
let expenseCategoriesChart = null;
let monthlyTrendChart = null;

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
    document.getElementById("expenseForm").reset();
    
    // Set default date to today again after form reset
    const today = new Date().toISOString().split('T')[0];
    document.getElementById("date").value = today;
    
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
    
    // Update charts with the expenses data
    updateCharts(expenses);
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

// Chart functions
function updateCharts(expenses) {
  renderIncomeExpenseChart(expenses);
  renderExpenseCategoriesChart(expenses);
  renderMonthlyTrendChart(expenses);
}

// Render Income vs Expense comparison chart
function renderIncomeExpenseChart(expenses) {
  const totalIncome = expenses
    .filter(exp => exp.type === 'Income')
    .reduce((sum, exp) => sum + parseFloat(exp.amount), 0);
  
  const totalExpense = expenses
    .filter(exp => exp.type === 'Expense')
    .reduce((sum, exp) => sum + parseFloat(exp.amount), 0);
  
  const ctx = document.getElementById('income-expense-chart').getContext('2d');
  
  // Destroy previous chart instance if it exists
  if (incomeExpenseChart) {
    incomeExpenseChart.destroy();
  }
  
  incomeExpenseChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Income', 'Expenses'],
      datasets: [{
        data: [totalIncome, totalExpense],
        backgroundColor: ['#4caf50', '#f44336'],
        borderColor: ['#388e3c', '#d32f2f'],
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom'
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              return `${label}: $${value.toFixed(2)}`;
            }
          }
        }
      }
    }
  });
}

// Render expense categories chart
function renderExpenseCategoriesChart(expenses) {
  // Only process expense transactions
  const expenseOnly = expenses.filter(exp => exp.type === 'Expense');
  
  // Group by category and sum amounts
  const categories = {};
  expenseOnly.forEach(exp => {
    const category = exp.category || 'Uncategorized';
    if (!categories[category]) {
      categories[category] = 0;
    }
    categories[category] += parseFloat(exp.amount);
  });
  
  // Sort categories by amount (descending)
  const sortedCategories = Object.entries(categories)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5); // Limit to top 5 categories
  
  const categoryLabels = sortedCategories.map(item => item[0]);
  const categoryAmounts = sortedCategories.map(item => item[1]);
  
  // Generate colors
  const backgroundColors = [
    '#ff7043', '#5c6bc0', '#26a69a', '#ec407a', '#ab47bc',
    '#7e57c2', '#66bb6a', '#ffa726', '#78909c', '#42a5f5'
  ];
  
  const ctx = document.getElementById('expense-categories-chart').getContext('2d');
  
  // Destroy previous chart instance if it exists
  if (expenseCategoriesChart) {
    expenseCategoriesChart.destroy();
  }
  
  expenseCategoriesChart = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: categoryLabels,
      datasets: [{
        data: categoryAmounts,
        backgroundColor: backgroundColors.slice(0, categoryLabels.length),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            boxWidth: 12
          }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.label || '';
              const value = context.raw || 0;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: $${value.toFixed(2)} (${percentage}%)`;
            }
          }
        }
      }
    }
  });
}

// Render monthly trend chart
function renderMonthlyTrendChart(expenses) {
  // Group transactions by month
  const monthlyData = {};
  
  expenses.forEach(exp => {
    const date = new Date(exp.date);
    const monthYear = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    
    if (!monthlyData[monthYear]) {
      monthlyData[monthYear] = { income: 0, expense: 0 };
    }
    
    if (exp.type === 'Income') {
      monthlyData[monthYear].income += parseFloat(exp.amount);
    } else {
      monthlyData[monthYear].expense += parseFloat(exp.amount);
    }
  });
  
  // Sort months chronologically
  const sortedMonths = Object.keys(monthlyData).sort();
  
  // Format labels to show month names
  const monthLabels = sortedMonths.map(monthYear => {
    const [year, month] = monthYear.split('-');
    const date = new Date(parseInt(year), parseInt(month) - 1, 1);
    return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  });
  
  const incomeData = sortedMonths.map(month => monthlyData[month].income);
  const expenseData = sortedMonths.map(month => monthlyData[month].expense);
  
  const ctx = document.getElementById('monthly-trend-chart').getContext('2d');
  
  // Destroy previous chart instance if it exists
  if (monthlyTrendChart) {
    monthlyTrendChart.destroy();
  }
  
  monthlyTrendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: monthLabels,
      datasets: [
        {
          label: 'Income',
          data: incomeData,
          borderColor: '#4caf50',
          backgroundColor: 'rgba(76, 175, 80, 0.1)',
          tension: 0.1,
          fill: true
        },
        {
          label: 'Expenses',
          data: expenseData,
          borderColor: '#f44336',
          backgroundColor: 'rgba(244, 67, 54, 0.1)',
          tension: 0.1,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: value => `$${value}`
          }
        }
      },
      plugins: {
        legend: {
          position: 'bottom'
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const label = context.dataset.label || '';
              const value = context.raw || 0;
              return `${label}: $${value.toFixed(2)}`;
            }
          }
        }
      }
    }
  });
}
