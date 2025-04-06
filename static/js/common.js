// Password toggle functionality
function setupPasswordToggles() {
    const toggles = document.querySelectorAll('.password-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const type = input.getAttribute('type');
            
            if (type === 'password') {
                input.setAttribute('type', 'text');
                this.innerHTML = '<i class="fas fa-eye-slash"></i>';
            } else {
                input.setAttribute('type', 'password');
                this.innerHTML = '<i class="fas fa-eye"></i>';
            }
        });
    });
}

// Form submission handling
function setupFormSubmissions() {
    const forms = document.querySelectorAll('form[data-loading]');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const buttons = this.querySelectorAll('button[type="submit"]');
            buttons.forEach(button => {
                const originalText = button.innerHTML;
                button.setAttribute('data-original-text', originalText);
                button.setAttribute('disabled', true);
                button.innerHTML = `<span class="spinner"></span> ${this.getAttribute('data-loading')}`;
            });
        });
    });
}

// Setup camera tooltips
function setupCameraTooltips() {
    const actionBtns = document.querySelectorAll('.action-btn[data-tooltip]');
    actionBtns.forEach(btn => {
        const tooltip = document.createElement('div');
        tooltip.className = 'camera-tooltip';
        tooltip.textContent = btn.getAttribute('data-tooltip');
        btn.appendChild(tooltip);
    });
}

// Initialize functionality when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    setupPasswordToggles();
    setupFormSubmissions();
    setupCameraTooltips();
});
