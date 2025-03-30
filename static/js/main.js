// Utility Functions
function showSpinner() {
    const spinner = `
        <div class="spinner-container">
            <div class="spinner"></div>
        </div>
    `;
    return spinner;
}

function showAlert(message, type = 'success') {
    const alert = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    const alertContainer = document.createElement('div');
    alertContainer.innerHTML = alert;
    document.querySelector('main').prepend(alertContainer);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        alertContainer.remove();
    }, 5000);
}

// API Calls
async function apiCall(url, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Something went wrong');
        }
        
        return result;
    } catch (error) {
        showAlert(error.message, 'danger');
        throw error;
    }
}

// Menu Management
async function uploadMenu(formData) {
    try {
        const response = await fetch('/menu/upload', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to upload menu');
        }
        
        return result;
    } catch (error) {
        showAlert(error.message, 'danger');
        throw error;
    }
}

async function addMenuItem(menuData) {
    return apiCall('/menu/items', 'POST', menuData);
}

async function updateMenuItem(itemId, menuData) {
    return apiCall(`/menu/items/${itemId}`, 'PUT', menuData);
}

async function deleteMenuItem(itemId) {
    return apiCall(`/menu/items/${itemId}`, 'DELETE');
}

// Order Management
async function createOrder(orderData) {
    return apiCall('/order/create', 'POST', orderData);
}

async function updateOrderStatus(orderId, status) {
    return apiCall(`/order/${orderId}/status`, 'PUT', { status });
}

async function processPayment(orderId, paymentData) {
    return apiCall(`/order/${orderId}/pay`, 'POST', paymentData);
}

async function submitFeedback(orderId, feedbackData) {
    return apiCall(`/order/${orderId}/feedback`, 'POST', feedbackData);
}

// Table Management
async function addTable(tableData) {
    return apiCall('/tables', 'POST', tableData);
}

async function generateQRCode(tableId) {
    return apiCall(`/menu/qr/${tableId}`);
}

// Event Handlers
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
    
    // Initialize popovers
    const popovers = document.querySelectorAll('[data-bs-toggle="popover"]');
    popovers.forEach(popover => new bootstrap.Popover(popover));
    
    // File upload preview
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const preview = document.querySelector('#imagePreview');
                    if (preview) {
                        preview.src = e.target.result;
                        preview.style.display = 'block';
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }
    
    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
});

// Dark Mode Toggle
function toggleDarkMode() {
    const theme = document.body.getAttribute('data-bs-theme');
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// Load saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
document.body.setAttribute('data-bs-theme', savedTheme); 