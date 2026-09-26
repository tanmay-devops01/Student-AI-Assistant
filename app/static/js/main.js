// Main JavaScript for Student AI Assistant
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl)
    });

    // Form submissions with loading states
    var forms = document.querySelectorAll('form[data-loading]');
    forms.forEach(function(form) {
        form.addEventListener('submit', function() {
            var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn) {
                var originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
                submitBtn.disabled = true;
                
                // Reset after form submission
                setTimeout(function() {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 3000);
            }
        });
    });

    // Confirmation dialogs for delete actions
    var deleteLinks = document.querySelectorAll('a[data-confirm], button[data-confirm]');
    deleteLinks.forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (!confirm(el.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

    // Auto-dismiss alerts after 5 seconds
    var alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Priority badge click to cycle
    var priorityBadges = document.querySelectorAll('.badge-priority-selectable');
    priorityBadges.forEach(function(badge) {
        badge.addEventListener('click', function() {
            var current = this.getAttribute('data-priority');
            var next = this.getAttribute('data-next-priority');
            if (next) {
                this.textContent = next.charAt(0).toUpperCase() + next.slice(1);
                this.className = 'badge badge-priority-' + next;
                this.setAttribute('data-priority', next);
            }
        });
    });
});

// Chart.js helper functions
function initChart(canvasId, config) {
    var ctx = document.getElementById(canvasId);
    if (ctx) {
        return new Chart(ctx, config);
    }
    return null;
}

function createBarChart(canvasId, labels, datasets, options) {
    var config = {
        type: 'bar',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: Object.assign({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }, options || {})
    };
    
    return initChart(canvasId, config);
}

function createDoughnutChart(canvasId, labels, data, options) {
    var config = {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#0d6efd',
                    '#198754',
                    '#fd7e14',
                    '#dc3545'
                ],
                borderWidth: 0
            }]
        },
        options: Object.assign({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            },
            cutout: '70%'
        }, options || {})
    };
    
    return initChart(canvasId, config);
}

// Handle file upload preview
function handleFileUpload(inputId, previewId) {
    var input = document.getElementById(inputId);
    var preview = document.getElementById(previewId);
    
    if (input && preview) {
        input.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                var file = this.files[0];
                var reader = new FileReader();
                
                reader.onload = function(e) {
                    preview.innerHTML = '<i class="fas fa-file-pdf fa-3x text-danger"></i><br>' +
                                       '<small class="text-muted">' + file.name + '</small><br>' +
                                       '<span class="text-success"><i class="fas fa-check-circle"></i> Ready for upload</span>';
                };
                
                reader.readAsDataURL(file);
            }
        });
    }
}

// Debounce function for search inputs
function debounce(func, wait) {
    var timeout;
    return function executedFunction() {
        var context = this;
        var args = arguments;
        var later = function() {
            timeout = null;
            func.apply(context, args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Format date for display
function formatDate(dateString) {
    if (!dateString) return '';
    var date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    var options = { year: 'numeric', month: 'short', day: 'numeric' };
    if (dateString.includes('T')) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    return date.toLocaleDateString('en-US', options);
}

// Calculate time remaining
function timeRemaining(deadlineString) {
    if (!deadlineString) return null;
    var deadline = new Date(deadlineString);
    var now = new Date();
    var diff = deadline - now;
    
    if (diff < 0) return { text: 'Overdue', class: 'text-danger' };
    if (diff < 3600000) return { text: Math.floor(diff / 60000) + ' min left', class: 'text-warning' };
    if (diff < 86400000) return { text: Math.floor(diff / 3600000) + ' hours left', class: 'text-warning' };
    if (diff < 604800000) return { text: Math.floor(diff / 86400000) + ' days left', class: 'text-info' };
    
    return { text: formatDate(deadlineString), class: '' };
}
