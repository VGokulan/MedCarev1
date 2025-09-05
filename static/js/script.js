// script.js
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    addActionButtonListeners();
});

function initializeTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const body = document.body;
    
    // Check for saved theme preference or respect OS preference
    const savedTheme = localStorage.getItem('theme') || 
                       (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    
    // Apply the saved theme
    if (savedTheme === 'dark') {
        body.setAttribute('data-theme', 'dark');
        if (themeToggle) themeToggle.classList.add('active');
    }
    
    // Theme toggle event
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const isDark = body.getAttribute('data-theme') === 'dark';
            if (isDark) {
                body.removeAttribute('data-theme');
                themeToggle.classList.remove('active');
                localStorage.setItem('theme', 'light');
            } else {
                body.setAttribute('data-theme', 'dark');
                themeToggle.classList.add('active');
                localStorage.setItem('theme', 'dark');
            }
        });
    }
}

// ... rest of the existing script.js code ...

// Function to add event listeners to action buttons
function addActionButtonListeners() {
    const viewButtons = document.querySelectorAll('.action-buttons .fa-eye');
    
    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            const patientId = this.closest('tr').querySelector('td:nth-child(2)').textContent;
            viewPatient(patientId);
        });
    });
}

// Function to view patient details
function viewPatient(patientId) {
    // In a real application, this would navigate to a patient details page
    showNotification(`Viewing details for patient ${patientId}`);
    
    // For now, we'll show a simple alert with the patient ID
    alert(`Patient Details for: ${patientId}\n\nThis would open a detailed view in a real application.`);
}

// Function to export patients
function exportPatients() {
    showNotification('Exporting patient data...');
    // In a real application, this would trigger a download
    alert('Patient export functionality would be implemented here.');
}

// Function to show notification
function showNotification(message) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.innerHTML = `
        <i class="fas fa-info-circle"></i>
        <span>${message}</span>
        <button class="close-notification">&times;</button>
    `;
    
    // Add styles if not already added
    if (!document.querySelector('#notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'notification-styles';
        styles.textContent = `
            .notification {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background-color: var(--bg-secondary);
                color: var(--text-primary);
                padding: 12px 16px;
                border-radius: 8px;
                border: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 1000;
                max-width: 400px;
                animation: slideInUp 0.3s ease-out;
            }
            
            .close-notification {
                background: none;
                border: none;
                color: var(--text-secondary);
                font-size: 18px;
                cursor: pointer;
                margin-left: auto;
            }
            
            @keyframes slideInUp {
                from { transform: translateY(100%); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
        `;
        document.head.appendChild(styles);
    }
    
    // Add close event
    notification.querySelector('.close-notification').addEventListener('click', function() {
        notification.remove();
    });
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 3000);
}

// Function to show error message
function showError(message) {
    // Create error notification
    const notification = document.createElement('div');
    notification.className = 'error-notification';
    notification.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
        <button class="close-notification">&times;</button>
    `;
    
    // Add styles if not already added
    if (!document.querySelector('#error-notification-styles')) {
        const styles = document.createElement('style');
        styles.id = 'error-notification-styles';
        styles.textContent = `
            .error-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background-color: #fef2f2;
                color: #dc2626;
                padding: 12px 16px;
                border-radius: 8px;
                border-left: 4px solid #dc2626;
                display: flex;
                align-items: center;
                gap: 8px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                z-index: 1000;
                max-width: 400px;
                animation: slideIn 0.3s ease-out;
            }
            
            .close-notification {
                background: none;
                border: none;
                color: #dc2626;
                font-size: 18px;
                cursor: pointer;
                margin-left: auto;
            }
            
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(styles);
    }
    
    // Add close event
    notification.querySelector('.close-notification').addEventListener('click', function() {
        notification.remove();
    });
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

// Debounce function to limit how often a function can be called
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}