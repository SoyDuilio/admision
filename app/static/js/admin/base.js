/* ============================================================
   POSTULANDO - JavaScript Base Admin
   static/js/admin/base.js
   
   Funciones compartidas para todos los dashboards admin
   ============================================================ */

// ============================================================
// UTILIDADES GENERALES
// ============================================================

/**
 * Mostrar notificación toast
 */
function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container') || createToastContainer();
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${getToastIcon(type)}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto remove
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.style.cssText = `
        position: fixed;
        top: 90px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
    `;
    document.body.appendChild(container);
    return container;
}

function getToastIcon(type) {
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    return icons[type] || icons.info;
}

/**
 * Confirmar acción con modal
 */
function confirmAction(message, onConfirm, onCancel = null) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal" style="max-width: 400px;">
            <div class="modal-header">
                <h3 class="modal-title">⚠️ Confirmar acción</h3>
            </div>
            <div class="modal-body">
                <p>${message}</p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-outline" id="btnCancelConfirm">Cancelar</button>
                <button class="btn btn-danger" id="btnConfirm">Confirmar</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('active'), 10);
    
    modal.querySelector('#btnConfirm').onclick = () => {
        closeModal(modal);
        if (onConfirm) onConfirm();
    };
    
    modal.querySelector('#btnCancelConfirm').onclick = () => {
        closeModal(modal);
        if (onCancel) onCancel();
    };
    
    modal.onclick = (e) => {
        if (e.target === modal) {
            closeModal(modal);
            if (onCancel) onCancel();
        }
    };
}

function closeModal(modal) {
    modal.classList.remove('active');
    setTimeout(() => modal.remove(), 300);
}

// ============================================================
// MANEJO DE PESTAÑAS
// ============================================================

/**
 * Inicializar sistema de pestañas
 */
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            
            // Desactivar todos
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            // Activar el seleccionado
            btn.classList.add('active');
            const content = document.getElementById(tabId);
            if (content) {
                content.classList.add('active');
            }
            
            // Guardar en localStorage
            localStorage.setItem('activeTab', tabId);
            
            // Disparar evento personalizado
            document.dispatchEvent(new CustomEvent('tabChanged', { detail: { tabId } }));
        });
    });
    
    // Restaurar pestaña activa
    const savedTab = localStorage.getItem('activeTab');
    if (savedTab) {
        const btn = document.querySelector(`[data-tab="${savedTab}"]`);
        if (btn) btn.click();
    }
}

// ============================================================
// MANEJO DE FORMULARIOS
// ============================================================

/**
 * Serializar formulario a objeto
 */
function serializeForm(form) {
    const formData = new FormData(form);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        if (data[key]) {
            if (!Array.isArray(data[key])) {
                data[key] = [data[key]];
            }
            data[key].push(value);
        } else {
            data[key] = value;
        }
    }
    
    return data;
}

/**
 * Validar formulario
 */
function validateForm(form) {
    const inputs = form.querySelectorAll('[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        removeError(input);
        
        if (!input.value.trim()) {
            showError(input, 'Este campo es requerido');
            isValid = false;
        } else if (input.type === 'email' && !isValidEmail(input.value)) {
            showError(input, 'Ingrese un email válido');
            isValid = false;
        } else if (input.dataset.pattern) {
            const regex = new RegExp(input.dataset.pattern);
            if (!regex.test(input.value)) {
                showError(input, input.dataset.errorMessage || 'Formato inválido');
                isValid = false;
            }
        }
    });
    
    return isValid;
}

function showError(input, message) {
    input.classList.add('error');
    const error = document.createElement('span');
    error.className = 'form-error';
    error.textContent = message;
    error.style.cssText = 'color: var(--danger); font-size: 0.75rem; margin-top: 4px; display: block;';
    input.parentNode.appendChild(error);
}

function removeError(input) {
    input.classList.remove('error');
    const error = input.parentNode.querySelector('.form-error');
    if (error) error.remove();
}

function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isValidDNI(dni) {
    return /^\d{8}$/.test(dni);
}

// ============================================================
// FETCH HELPERS
// ============================================================

/**
 * Hacer petición fetch con manejo de errores
 */
async function fetchAPI(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    const config = { ...defaultOptions, ...options };
    
    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }
    
    try {
        const response = await fetch(url, config);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.error || 'Error en la petición');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * GET request
 */
async function apiGet(url) {
    return fetchAPI(url, { method: 'GET' });
}

/**
 * POST request
 */
async function apiPost(url, data) {
    return fetchAPI(url, { method: 'POST', body: data });
}

/**
 * PUT request
 */
async function apiPut(url, data) {
    return fetchAPI(url, { method: 'PUT', body: data });
}

/**
 * DELETE request
 */
async function apiDelete(url) {
    return fetchAPI(url, { method: 'DELETE' });
}

// ============================================================
// UPLOAD DE ARCHIVOS
// ============================================================

/**
 * Inicializar zona de upload
 */
function initUploadZone(zoneId, options = {}) {
    const zone = document.getElementById(zoneId);
    if (!zone) return;
    
    const input = zone.querySelector('input[type="file"]');
    const preview = zone.querySelector('.file-preview') || createPreviewElement(zone);
    
    // Click para abrir selector
    zone.addEventListener('click', (e) => {
        if (e.target !== input) {
            input.click();
        }
    });
    
    // Drag and drop
    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('drag-over');
    });
    
    zone.addEventListener('dragleave', () => {
        zone.classList.remove('drag-over');
    });
    
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length) {
            input.files = files;
            handleFileSelect(input, preview, options);
        }
    });
    
    // Cambio de archivo
    input.addEventListener('change', () => {
        handleFileSelect(input, preview, options);
    });
}

function createPreviewElement(zone) {
    const preview = document.createElement('div');
    preview.className = 'file-preview hidden';
    zone.appendChild(preview);
    return preview;
}

function handleFileSelect(input, preview, options) {
    const file = input.files[0];
    if (!file) {
        preview.classList.add('hidden');
        return;
    }
    
    // Validar tipo
    if (options.accept) {
        const validTypes = options.accept.split(',').map(t => t.trim());
        const fileType = '.' + file.name.split('.').pop().toLowerCase();
        if (!validTypes.includes(fileType) && !validTypes.includes(file.type)) {
            showToast('Tipo de archivo no permitido', 'error');
            input.value = '';
            return;
        }
    }
    
    // Validar tamaño
    if (options.maxSize && file.size > options.maxSize) {
        const maxMB = (options.maxSize / 1024 / 1024).toFixed(1);
        showToast(`El archivo excede el tamaño máximo de ${maxMB}MB`, 'error');
        input.value = '';
        return;
    }
    
    // Mostrar preview
    const icon = getFileIcon(file.name);
    const size = formatFileSize(file.size);
    
    preview.innerHTML = `
        <span class="icon">${icon}</span>
        <div class="info">
            <div class="name">${file.name}</div>
            <div class="size">${size}</div>
        </div>
        <button type="button" class="remove" onclick="clearFileInput('${input.id}')">×</button>
    `;
    preview.classList.remove('hidden');
    
    // Callback
    if (options.onSelect) {
        options.onSelect(file);
    }
}

function clearFileInput(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.value = '';
        const preview = input.closest('.upload-zone').querySelector('.file-preview');
        if (preview) preview.classList.add('hidden');
    }
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        xlsx: '📊',
        xls: '📊',
        csv: '📄',
        txt: '📝',
        pdf: '📕'
    };
    return icons[ext] || '📄';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// ============================================================
// TABLA CON SELECCIÓN
// ============================================================

/**
 * Inicializar tabla con selección múltiple
 */
function initSelectableTable(tableId, options = {}) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    const checkAll = table.querySelector('.check-all');
    const checkboxes = table.querySelectorAll('.row-check');
    const bulkActions = document.querySelector(options.bulkActionsSelector || '.bulk-actions');
    
    // Seleccionar todos
    if (checkAll) {
        checkAll.addEventListener('change', () => {
            checkboxes.forEach(cb => {
                cb.checked = checkAll.checked;
            });
            updateBulkActions();
        });
    }
    
    // Selección individual
    checkboxes.forEach(cb => {
        cb.addEventListener('change', updateBulkActions);
    });
    
    function updateBulkActions() {
        const selected = table.querySelectorAll('.row-check:checked');
        const count = selected.length;
        
        if (bulkActions) {
            if (count > 0) {
                bulkActions.classList.add('active');
                const countEl = bulkActions.querySelector('.count');
                if (countEl) countEl.textContent = `${count} seleccionado(s)`;
            } else {
                bulkActions.classList.remove('active');
            }
        }
        
        // Actualizar estado del checkAll
        if (checkAll) {
            checkAll.checked = count === checkboxes.length;
            checkAll.indeterminate = count > 0 && count < checkboxes.length;
        }
        
        // Callback
        if (options.onSelectionChange) {
            const selectedIds = Array.from(selected).map(cb => cb.value);
            options.onSelectionChange(selectedIds);
        }
    }
    
    return {
        getSelectedIds: () => Array.from(table.querySelectorAll('.row-check:checked')).map(cb => cb.value),
        clearSelection: () => {
            checkboxes.forEach(cb => cb.checked = false);
            if (checkAll) checkAll.checked = false;
            updateBulkActions();
        }
    };
}

// ============================================================
// PAGINACIÓN
// ============================================================

/**
 * Crear controles de paginación
 */
function createPagination(containerId, currentPage, totalPages, onPageChange) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    let html = '<div class="pagination">';
    
    // Botón anterior
    html += `<button class="pagination-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">←</button>`;
    
    // Números de página
    const range = getPaginationRange(currentPage, totalPages);
    range.forEach(page => {
        if (page === '...') {
            html += '<span class="pagination-dots">...</span>';
        } else {
            html += `<button class="pagination-btn ${page === currentPage ? 'active' : ''}" onclick="goToPage(${page})">${page}</button>`;
        }
    });
    
    // Botón siguiente
    html += `<button class="pagination-btn" ${currentPage === totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">→</button>`;
    
    html += '</div>';
    container.innerHTML = html;
    
    // Función global para cambiar página
    window.goToPage = (page) => {
        if (page >= 1 && page <= totalPages) {
            onPageChange(page);
        }
    };
}

function getPaginationRange(current, total) {
    const delta = 2;
    const range = [];
    const rangeWithDots = [];
    
    for (let i = 1; i <= total; i++) {
        if (i === 1 || i === total || (i >= current - delta && i <= current + delta)) {
            range.push(i);
        }
    }
    
    let prev;
    for (let i of range) {
        if (prev) {
            if (i - prev === 2) {
                rangeWithDots.push(prev + 1);
            } else if (i - prev !== 1) {
                rangeWithDots.push('...');
            }
        }
        rangeWithDots.push(i);
        prev = i;
    }
    
    return rangeWithDots;
}

// ============================================================
// FORMATEO
// ============================================================

/**
 * Formatear fecha
 */
function formatDate(date, format = 'short') {
    const d = new Date(date);
    
    if (format === 'short') {
        return d.toLocaleDateString('es-PE');
    } else if (format === 'long') {
        return d.toLocaleDateString('es-PE', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    } else if (format === 'datetime') {
        return d.toLocaleString('es-PE');
    }
    
    return d.toLocaleDateString('es-PE');
}

/**
 * Formatear número
 */
function formatNumber(num) {
    return new Intl.NumberFormat('es-PE').format(num);
}

// ============================================================
// DEBOUNCE Y THROTTLE
// ============================================================

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

// ============================================================
// INICIALIZACIÓN AUTOMÁTICA
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar pestañas si existen
    if (document.querySelector('.tab-btn')) {
        initTabs();
    }
    
    // Agregar estilos de toast dinámicamente
    if (!document.getElementById('toast-styles')) {
        const style = document.createElement('style');
        style.id = 'toast-styles';
        style.textContent = `
            .toast {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 12px 16px;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                transform: translateX(120%);
                transition: transform 0.3s ease;
                min-width: 280px;
            }
            .toast.show { transform: translateX(0); }
            .toast-success { border-left: 4px solid #10b981; }
            .toast-error { border-left: 4px solid #ef4444; }
            .toast-warning { border-left: 4px solid #f59e0b; }
            .toast-info { border-left: 4px solid #3b82f6; }
            .toast-message { flex: 1; font-size: 0.9rem; }
            .toast-close {
                background: none;
                border: none;
                font-size: 1.2rem;
                color: #94a3b8;
                cursor: pointer;
            }
        `;
        document.head.appendChild(style);
    }
});

// Exportar para uso en módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showToast,
        confirmAction,
        fetchAPI,
        apiGet,
        apiPost,
        apiPut,
        apiDelete,
        validateForm,
        debounce,
        throttle
    };
}