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
        
        console.log(`Making ${method} request to ${url}`, data);
        const response = await fetch(url, options);
        
        let result;
        try {
            result = await response.json();
        } catch (e) {
            console.error('Failed to parse JSON response:', e);
            throw new Error('Server returned an invalid response');
        }
        
        if (!response.ok) {
            const errorMsg = result.message || result.error || 'Something went wrong';
            console.error(`API error (${response.status}):`, errorMsg);
            throw new Error(errorMsg);
        }
        
        return result;
    } catch (error) {
        console.error('API call failed:', error);
        showAlert(error.message || 'Failed to complete operation', 'danger');
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
    return apiCall(`/api/orders/${orderId}/status`, 'PUT', { status });
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

async function autoAddTable() {
    return apiCall('/auto-add-table', 'POST');
}

async function generateQRCode(tableId) {
    return apiCall(`/table/qr/${tableId}`);
}

async function deleteTableApi(tableId) {
    return apiCall(`/table/delete/${tableId}`, 'DELETE');
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

// Make functions available globally
window.addTable = addTable;
window.autoAddTable = autoAddTable;
window.generateQRCode = generateQRCode;
window.deleteTableApi = deleteTableApi;
window.deleteTable = async function(tableId) {
    if (confirm('Are you sure you want to delete this table? This cannot be undone.')) {
        try {
            showAlert('Deleting table...', 'info');
            const result = await deleteTableApi(tableId);
            if (result.success) {
                showAlert('Table deleted successfully', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                // More descriptive error message
                let errorMessage = result.message || 'Failed to delete table';
                console.error('Delete table error:', errorMessage);
                
                // Enhanced user-friendly message for common error cases
                if (errorMessage.includes('active orders')) {
                    errorMessage = 'Cannot delete table with active orders. Please complete or cancel all orders for this table first.';
                } else if (errorMessage.includes('Unauthorized')) {
                    errorMessage = 'You do not have permission to delete this table.';
                }
                
                showAlert(errorMessage, 'danger');
            }
        } catch (error) {
            console.error('Error deleting table:', error);
            // Enhanced error handler with more details
            const errorDetail = error.message || 'Unknown error';
            showAlert(`Error deleting table: ${errorDetail}. Please check the console for more details.`, 'danger');
        }
    }
};

// Add a global showAlert function
window.showAlert = function(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '1050';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
};

// Add utility functions for testing
function runTests() {
    console.log("Running table management tests...");
    
    // Test 1: Add a new table
    testAddTable();
    
    // Test 2: Delete a table
    testDeleteTable();
    
    // Test 3: Refresh QR code
    testRefreshQRCode();
    
    console.log("Tests completed!");
}

async function testAddTable() {
    console.log("Test: Adding a new table");
    try {
        const result = await window.autoAddTable();
        console.assert(result.success === true, "Table addition failed");
        console.log("✓ Table added successfully:", result.table.number);
    } catch (error) {
        console.error("✗ Table addition test failed:", error);
    }
}

async function testDeleteTable(tableId) {
    console.log("Test: Deleting a table");
    if (!tableId) {
        // Get the last table from the page
        const tableElements = document.querySelectorAll('.table-card');
        if (tableElements.length === 0) {
            console.log("No tables to delete for testing");
            return;
        }
        
        // Find a delete button and extract the table ID
        const deleteButton = tableElements[tableElements.length - 1].querySelector('button[onclick^="deleteTable"]');
        if (!deleteButton) {
            console.log("No delete button found for testing");
            return;
        }
        
        const onclickAttr = deleteButton.getAttribute('onclick');
        tableId = onclickAttr.match(/deleteTable\((\d+)\)/)[1];
    }
    
    try {
        // Mock the confirm function to always return true during testing
        const originalConfirm = window.confirm;
        window.confirm = () => true;
        
        const result = await window.deleteTableApi(tableId);
        console.assert(result.success === true, "Table deletion failed");
        console.log("✓ Table deleted successfully");
        
        // Restore the original confirm function
        window.confirm = originalConfirm;
    } catch (error) {
        console.error("✗ Table deletion test failed:", error);
    }
}

async function testRefreshQRCode(tableId) {
    console.log("Test: Refreshing QR code");
    if (!tableId) {
        // Get the first table from the page
        const tableElements = document.querySelectorAll('.table-card');
        if (tableElements.length === 0) {
            console.log("No tables available for QR code testing");
            return;
        }
        
        // Find a refresh button and extract the table ID
        const refreshButton = tableElements[0].querySelector('button[onclick^="refreshQRCode"]');
        if (!refreshButton) {
            console.log("No refresh button found for testing");
            return;
        }
        
        const onclickAttr = refreshButton.getAttribute('onclick');
        tableId = onclickAttr.match(/refreshQRCode\((\d+)\)/)[1];
    }
    
    try {
        const result = await window.generateQRCode(tableId);
        console.assert(result.success === true, "QR code refresh failed");
        console.log("✓ QR code refreshed successfully");
    } catch (error) {
        console.error("✗ QR code refresh test failed:", error);
    }
}

// Make the test functions available globally
window.runTableTests = runTests;
window.testAddTable = testAddTable;
window.testDeleteTable = testDeleteTable;
window.testRefreshQRCode = testRefreshQRCode;

// More comprehensive test functions for table management
async function runComprehensiveTableTests() {
    console.log("Running comprehensive table tests...");
    
    // Test table CRUD operations
    await testTableCreation();
    await testTableDeletion();
    await testQRCodeGeneration();
    
    console.log("Comprehensive tests completed!");
}

async function testTableCreation() {
    console.log("=== Testing Table Creation ===");
    try {
        // First, get original table count
        const tableElements = document.querySelectorAll('.table-card');
        const originalCount = tableElements.length;
        console.log(`Original table count: ${originalCount}`);
        
        // Create a new table
        console.log("Adding a new table...");
        const result = await window.autoAddTable();
        
        if (result.success) {
            console.log(`✓ Table #${result.table.number} created successfully`);
            
            // Wait for page reload
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            // Check if table count increased
            const newElements = document.querySelectorAll('.table-card');
            const newCount = newElements.length;
            
            if (newCount > originalCount) {
                console.log(`✓ Table count increased from ${originalCount} to ${newCount}`);
            } else {
                console.error(`✗ Table count did not increase as expected`);
            }
        } else {
            console.error(`✗ Table creation failed: ${result.message}`);
        }
    } catch (error) {
        console.error("✗ Table creation test failed:", error);
    }
}

async function testTableDeletion() {
    console.log("=== Testing Table Deletion ===");
    try {
        // Get current table count
        const tableElements = document.querySelectorAll('.table-card');
        if (tableElements.length === 0) {
            console.log("No tables available for deletion testing");
            return;
        }
        
        const originalCount = tableElements.length;
        console.log(`Current table count: ${originalCount}`);
        
        // Get the last table ID for deletion
        const lastTable = tableElements[tableElements.length - 1];
        const deleteButton = lastTable.querySelector('button[onclick^="deleteTable"]');
        
        if (!deleteButton) {
            console.log("No delete button found for testing");
            return;
        }
        
        const onclickAttr = deleteButton.getAttribute('onclick');
        const tableId = onclickAttr.match(/deleteTable\((\d+)\)/)[1];
        
        console.log(`Attempting to delete table ID: ${tableId}`);
        
        // Mock the confirm function to always return true during testing
        const originalConfirm = window.confirm;
        window.confirm = () => true;
        
        // Call the deleteTable function
        await window.deleteTable(tableId);
        
        // Restore the original confirm function
        window.confirm = originalConfirm;
        
        // Wait for the delete operation and page reload
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Check if table count decreased
        const newElements = document.querySelectorAll('.table-card');
        const newCount = newElements.length;
        
        if (newCount < originalCount) {
            console.log(`✓ Table count decreased from ${originalCount} to ${newCount}`);
        } else {
            console.error(`✗ Table count did not decrease as expected`);
            console.log("Note: This might be because the table was soft-deleted (marked as 'deleted' in DB)");
        }
        
    } catch (error) {
        console.error("✗ Table deletion test failed:", error);
    }
}

async function testQRCodeGeneration() {
    console.log("=== Testing QR Code Generation ===");
    try {
        // Find a table without QR code if possible
        const tableElements = document.querySelectorAll('.table-card');
        if (tableElements.length === 0) {
            console.log("No tables available for QR code testing");
            return;
        }
        
        let targetTable = null;
        let tableId = null;
        
        // Try to find a table without QR code first
        for (const table of tableElements) {
            const qrPlaceholder = table.querySelector('.qr-placeholder');
            if (qrPlaceholder) {
                const refreshButton = qrPlaceholder.querySelector('button[onclick^="refreshQRCode"]');
                if (refreshButton) {
                    const onclickAttr = refreshButton.getAttribute('onclick');
                    tableId = onclickAttr.match(/refreshQRCode\((\d+)\)/)[1];
                    targetTable = table;
                    console.log(`Found table without QR code: ${tableId}`);
                    break;
                }
            }
        }
        
        // If all tables have QR codes, use the first table
        if (!targetTable) {
            targetTable = tableElements[0];
            const refreshButton = targetTable.querySelector('button[onclick^="refreshQRCode"]');
            if (refreshButton) {
                const onclickAttr = refreshButton.getAttribute('onclick');
                tableId = onclickAttr.match(/refreshQRCode\((\d+)\)/)[1];
                console.log(`Using table with existing QR code: ${tableId}`);
            }
        }
        
        if (!tableId) {
            console.log("Could not find a suitable table for QR code testing");
            return;
        }
        
        console.log(`Refreshing QR code for table ID: ${tableId}`);
        
        // Call the refreshQRCode function
        await window.refreshQRCode(tableId);
        
        // Wait for the operation to complete and page to reload
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        console.log("✓ QR code refresh test completed");
        
    } catch (error) {
        console.error("✗ QR code refresh test failed:", error);
    }
}

// Make comprehensive test functions available globally
window.runComprehensiveTableTests = runComprehensiveTableTests;
window.testTableCreation = testTableCreation;
window.testTableDeletion = testTableDeletion;
window.testQRCodeGeneration = testQRCodeGeneration; 