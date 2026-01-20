/**
 * Ye - Frontend interaction script
 * Handles form submission, progress display, result loading, etc.
 */

// Initialize after page load completes
document.addEventListener('DOMContentLoaded', function() {
    console.log('Ye - Frontend initialized');

    // Initialize tooltips
    initTooltips();

    // Initialize form validation
    initFormValidation();
});

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialize form validation
 */
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');

    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

/**
 * Show loading progress
 * @param {string} message - Progress message
 */
function showProgress(message) {
    const progressArea = document.getElementById('progressArea');
    const progressText = document.getElementById('progressText');

    if (progressArea && progressText) {
        progressArea.style.display = 'block';
        progressText.textContent = message;
    }
}

/**
 * Hide loading progress
 */
function hideProgress() {
    const progressArea = document.getElementById('progressArea');
    if (progressArea) {
        progressArea.style.display = 'none';
    }
}

/**
 * Show error message
 * @param {string} message - Error message
 */
function showError(message) {
    alert('Error: ' + message);
}

/**
 * Show success message
 * @param {string} message - Success message
 */
function showSuccess(message) {
    alert('Success: ' + message);
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showSuccess('Copied to clipboard!');
    }, function() {
        showError('Failed to copy to clipboard');
    });
}

/**
 * Format number (add thousands separator)
 * @param {number} num - Number
 * @returns {string} Formatted string
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Format date
 * @param {string} dateString - Date string
 * @returns {string} Formatted date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time (milliseconds)
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function
 * @param {Function} func - Function to throttle
 * @param {number} limit - Limit time (milliseconds)
 * @returns {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
