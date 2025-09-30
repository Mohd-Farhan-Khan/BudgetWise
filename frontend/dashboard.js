const API_BASE = "http://127.0.0.1:5001"; // updated port
// Also expose on a global namespace to share with other scripts
window.BUDGETWISE_API_BASE = API_BASE;

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

// UI Enhancement Functions
function initializeDashboard() {
  // Set current date in welcome banner
  const currentDate = new Date();
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  document.getElementById('current-date').textContent = currentDate.toLocaleDateString('en-US', options);
  
  // Mobile menu toggle
  const sidebarToggleBtn = document.createElement('button');
  sidebarToggleBtn.className = 'mobile-menu-toggle';
  sidebarToggleBtn.innerHTML = '<i class="fas fa-bars"></i>';
  document.querySelector('.dashboard-header').prepend(sidebarToggleBtn);
  
  // Create overlay for mobile menu
  const overlay = document.createElement('div');
  overlay.className = 'sidebar-overlay';
  document.querySelector('.dashboard-container').appendChild(overlay);
  
  // Add event listeners for mobile menu
  sidebarToggleBtn.addEventListener('click', () => {
    document.querySelector('.sidebar').classList.toggle('active');
    overlay.classList.toggle('active');
  });
  
  overlay.addEventListener('click', () => {
    document.querySelector('.sidebar').classList.remove('active');
    overlay.classList.remove('active');
  });
  
  // Initialize filter for transactions
  document.getElementById('filter-transactions').addEventListener('input', function() {
    const filterText = this.value.toLowerCase();
    const transactions = document.querySelectorAll('#expenseList li');
    
    transactions.forEach(transaction => {
      const category = transaction.querySelector('.col-category').textContent.toLowerCase();
      const note = transaction.querySelector('.col-note').textContent.toLowerCase();
      const date = transaction.querySelector('.col-date').textContent.toLowerCase();
      
      if (category.includes(filterText) || note.includes(filterText) || date.includes(filterText)) {
        transaction.style.display = '';
      } else {
        transaction.style.display = 'none';
      }
    });
  });
  
  // Period selector for charts
  document.getElementById('chart-period').addEventListener('change', function() {
    // Reload expenses with period filter
    loadExpenses();
  });
  
  // Menu item click handlers
  document.querySelectorAll('.sidebar-menu a').forEach(menuItem => {
    menuItem.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Remove active class from all menu items
      document.querySelectorAll('.sidebar-menu li').forEach(item => {
        item.classList.remove('active');
      });
      
      // Add active class to clicked item's parent
      this.parentElement.classList.add('active');
      
      // Handle navigation (for now just scroll to relevant section)
      const targetSection = this.getAttribute('href').substring(1);
      let targetElement;
      
      switch(targetSection) {
        case 'dashboard':
          targetElement = document.querySelector('.welcome-banner');
          break;
        case 'transactions':
          targetElement = document.querySelector('.transaction-history-section');
          break;
        case 'analytics':
          targetElement = document.querySelector('.charts-section');
          break;
        default:
          targetElement = document.querySelector('.welcome-banner');
      }
      
      if (targetElement) {
        targetElement.scrollIntoView({ behavior: 'smooth' });
        
        // Close mobile menu if open
        document.querySelector('.sidebar').classList.remove('active');
        document.querySelector('.sidebar-overlay').classList.remove('active');
      }
    });
  });
  
  // Initialize Load More button
  document.getElementById('load-more').addEventListener('click', function() {
    // This would fetch more transactions in a real implementation
    this.textContent = 'No more transactions';
    this.disabled = true;
  });
}
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
  
  const submitButton = e.target.querySelector('button[type="submit"]');
  const originalText = submitButton.innerHTML;
  submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
  submitButton.disabled = true;
  
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

    // Show success notification
    showNotification((data && (data.message || data.msg)) || "Transaction added successfully");
    
    document.getElementById("expenseForm").reset();
    
    // Set default date to today again after form reset
    const today = new Date().toISOString().split('T')[0];
    document.getElementById("date").value = today;
    
    loadExpenses();
  } catch (err) {
    console.error("Error adding expense:", err);
    alert("Failed to add transaction. Please try again.");
  } finally {
    submitButton.innerHTML = originalText;
    submitButton.disabled = false;
  }
});

// Show notification function
function showNotification(message) {
  const notification = document.createElement('div');
  notification.className = 'notification';
  notification.innerHTML = `
    <div class="notification-content">
      <i class="fas fa-check-circle"></i>
      <span>${message}</span>
    </div>
    <button class="notification-close"><i class="fas fa-times"></i></button>
  `;
  
  document.body.appendChild(notification);
  
  // Add styles for notification
  const style = document.createElement('style');
  style.textContent = `
    .notification {
      position: fixed;
      top: 20px;
      right: 20px;
      background-color: #4caf50;
      color: white;
      padding: 15px 20px;
      border-radius: 8px;
      box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 1000;
      animation: slideIn 0.3s forwards;
    }
    .notification-content {
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .notification-close {
      background: none;
      border: none;
      color: white;
      cursor: pointer;
      font-size: 16px;
      opacity: 0.8;
      margin-left: 15px;
    }
    .notification-close:hover {
      opacity: 1;
    }
    @keyframes slideIn {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
  
  // Close button handler
  notification.querySelector('.notification-close').addEventListener('click', () => {
    notification.style.animation = 'slideOut 0.3s forwards';
    setTimeout(() => {
      notification.remove();
    }, 300);
  });
  
  // Auto-close after 5 seconds
  setTimeout(() => {
    if (document.body.contains(notification)) {
      notification.style.animation = 'slideOut 0.3s forwards';
      setTimeout(() => {
        notification.remove();
      }, 300);
    }
  }, 5000);
}

// Load expenses for the authenticated user
async function loadExpenses() {
  if (!checkAuth()) return;
  
  try {
    // Show loading state
    const expenseList = document.getElementById("expenseList");
    expenseList.innerHTML = `
      <li style="display: flex; justify-content: center; padding: 30px;">
        <i class="fas fa-spinner fa-spin" style="font-size: 24px; color: #757575;"></i>
      </li>
    `;
    
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
      expenseList.innerHTML = `
        <li style="text-align: center; padding: 20px; color: #f44336;">
          <i class="fas fa-exclamation-circle"></i> ${errMsg}
        </li>
      `;
      return;
    }

    const expenses = await res.json();
    expenseList.innerHTML = "";
    
    if (expenses.length === 0) {
      expenseList.innerHTML = `
        <li style="text-align: center; padding: 30px; color: #757575;">
          <i class="fas fa-inbox" style="font-size: 32px; margin-bottom: 10px; display: block;"></i>
          No transactions found. Add your first transaction!
        </li>
      `;
      
      // Reset summary cards
      document.getElementById("total-income").textContent = "$0.00";
      document.getElementById("total-expense").textContent = "$0.00";
      document.getElementById("balance").textContent = "$0.00";
      
      // Show empty state charts
      updateCharts([]);
      return;
    }
    
    let totalExpense = 0;
    let totalIncome = 0;
    
    // Apply period filter if set
    const period = document.getElementById('chart-period').value;
    let filteredExpenses = expenses;
    
    if (period !== 'all') {
      const now = new Date();
      const startDate = new Date();
      
      if (period === 'month') {
        startDate.setMonth(now.getMonth() - 1);
      } else if (period === 'quarter') {
        startDate.setMonth(now.getMonth() - 3);
      } else if (period === 'year') {
        startDate.setFullYear(now.getFullYear() - 1);
      }
      
      filteredExpenses = expenses.filter(exp => {
        const expDate = new Date(exp.date);
        return expDate >= startDate;
      });
    }
    
    // Process all expenses for totals (not just filtered ones)
    expenses.forEach(exp => {
      if (exp.type === 'Income') {
        totalIncome += parseFloat(exp.amount);
      } else {
        totalExpense += parseFloat(exp.amount);
      }
      
      const li = document.createElement("li");
      li.className = exp.type.toLowerCase();
      
      const formattedDate = new Date(exp.date).toLocaleDateString();
      
      li.innerHTML = `
        <span class="col-date">${formattedDate}</span>
        <span class="col-category">${exp.category || 'Uncategorized'}</span>
        <span class="col-note">${exp.note || '-'}</span>
        <span class="col-amount">${exp.type === 'Income' ? '+' : '-'}$${parseFloat(exp.amount).toFixed(2)}</span>
      `;
      expenseList.appendChild(li);
    });
    
    // Update summary
    document.getElementById("total-expense").textContent = `$${totalExpense.toFixed(2)}`;
    document.getElementById("total-income").textContent = `$${totalIncome.toFixed(2)}`;
    document.getElementById("balance").textContent = `$${(totalIncome - totalExpense).toFixed(2)}`;
    
    // Update charts with filtered expenses data
    updateCharts(filteredExpenses);
    
    // If we have more than 20 transactions, enable load more button
    if (expenses.length > 20) {
      document.getElementById('load-more').disabled = false;
      document.getElementById('load-more').textContent = 'Load More';
    } else {
      document.getElementById('load-more').disabled = true;
      document.getElementById('load-more').textContent = 'No more transactions';
    }
  } catch (err) {
    console.error("Error loading expenses:", err);
    document.getElementById("expenseList").innerHTML = `
      <li style="text-align: center; padding: 20px; color: #f44336;">
        <i class="fas fa-exclamation-triangle"></i> Error loading transactions. Please try again.
      </li>
    `;
  }
}

// Setup user info in the dashboard
function setupUserInfo() {
  if (!checkAuth()) return;
  
  const user = getUser();
  document.getElementById("username-display").textContent = user.username;
  document.getElementById("username-display2").textContent = user.username;
  document.getElementById("logout-btn").addEventListener("click", logout);
}

// Initialize dashboard
window.addEventListener('load', () => {
  setupUserInfo();
  initializeDashboard();
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
  
  // Check if we have any data
  if (categoryLabels.length === 0) {
    // Show empty state
    categoryLabels.push('No Data');
    categoryAmounts.push(1);
    
    expenseCategoriesChart = new Chart(ctx, {
      type: 'pie',
      data: {
        labels: categoryLabels,
        datasets: [{
          data: categoryAmounts,
          backgroundColor: ['#e0e0e0'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            enabled: false
          }
        }
      }
    });
    return;
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
  
  // Check if we have any data
  if (monthLabels.length === 0) {
    // Show empty state
    monthlyTrendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['No Data'],
        datasets: [
          {
            label: 'Income',
            data: [0],
            borderColor: '#e0e0e0',
            backgroundColor: 'rgba(224, 224, 224, 0.1)',
            borderDashed: [5, 5]
          },
          {
            label: 'Expenses',
            data: [0],
            borderColor: '#e0e0e0',
            backgroundColor: 'rgba(224, 224, 224, 0.1)',
            borderDashed: [5, 5]
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
            display: false
          },
          tooltip: {
            enabled: false
          }
        }
      }
    });
    return;
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
