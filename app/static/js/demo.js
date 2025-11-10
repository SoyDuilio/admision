// ==============================================
// POSTULANDO DEMO - JAVASCRIPT PRINCIPAL
// ==============================================

document.addEventListener('DOMContentLoaded', function() {

    cargarPostulantes();
    
    // ==============================================
    // ELEMENTOS DEL DOM
    // ==============================================
    
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    
    const captureArea = document.getElementById('capture-area');
    if (captureArea) {  // ← Agregar esta verificación
        captureArea.addEventListener('click', function() {
            fileInput.click();
        });
    }

    const fileInput = document.getElementById('file-input');
    const imagePreview = document.getElementById('image-preview');
    const previewImage = document.getElementById('preview-image');
    const previewInfo = document.getElementById('preview-info');
    const btnProcesar = document.getElementById('btn-procesar');
    const btnLimpiar = document.getElementById('btn-limpiar');
    const btnCalificarTodos = document.getElementById('btn-calificar-todos');
    const btnVerResultados = document.getElementById('btn-ver-resultados');
    const resultadoCalificacion = document.getElementById('resultado-calificacion');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    // Selectores de configuración
    const selectPostulante = document.getElementById('postulante');
    const selectAPI = document.getElementById('api-vision');
    
    let imagenActual = null;
    
    // ==============================================
    // SISTEMA DE TABS
    // ==============================================
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const target = this.getAttribute('data-tab');
            
            // Remover active de todos los tabs
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));
            
            // Activar el tab seleccionado
            this.classList.add('active');
            document.getElementById(target).classList.add('active');
        });
    });
    
    // ==============================================
    // CAPTURA DE IMAGEN
    // ==============================================
    
    captureArea.addEventListener('click', function() {
        fileInput.click();
    });
    
    captureArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('active');
    });
    
    captureArea.addEventListener('dragleave', function() {
        this.classList.remove('active');
    });
    
    captureArea.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('active');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });
    
    fileInput.addEventListener('change', function(e) {
        if (this.files.length > 0) {
            handleFile(this.files[0]);
        }
    });
    
    // ==============================================
    // MANEJO DE ARCHIVO
    // ==============================================
    
    function handleFile(file) {
        // Validar que sea imagen
        if (!file.type.startsWith('image/')) {
            showAlert('Por favor selecciona una imagen válida', 'danger');
            return;
        }
        
        // Validar tamaño (máx 5MB)
        if (file.size > 5 * 1024 * 1024) {
            showAlert('La imagen no debe superar 5MB', 'danger');
            return;
        }
        
        imagenActual = file;
        
        // Mostrar preview
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImage.src = e.target.result;
            imagePreview.classList.add('show');
            
            // Actualizar info
            const info = `
                <p><strong>Archivo:</strong> ${file.name}</p>
                <p><strong>Tamaño:</strong> ${formatFileSize(file.size)}</p>
                <p><strong>Tipo:</strong> ${file.type}</p>
            `;
            previewInfo.innerHTML = info;
            
            // Habilitar botón procesar
            btnProcesar.disabled = false;
        };
        reader.readAsDataURL(file);
    }
    
    // ==============================================
    // PROCESAR IMAGEN
    // ==============================================
    
    btnProcesar.addEventListener('click', async function() {
        if (!imagenActual) {
            showAlert('Por favor selecciona una imagen primero', 'warning');
            return;
        }
        
        const postulanteId = selectPostulante.value;
        const apiVision = selectAPI.value;
        
        if (!postulanteId) {
            showAlert('Por favor selecciona un postulante', 'warning');
            return;
        }
        
        // Mostrar loading
        showLoading('Procesando imagen con ' + apiVision.toUpperCase() + '...');
        
        // Crear FormData
        const formData = new FormData();
        formData.append('imagen', imagenActual);
        formData.append('postulante_id', postulanteId);
        formData.append('api_vision', apiVision);
        
        try {
            const response = await fetch('/api/procesar-hoja', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            hideLoading();
            
            if (response.ok) {
                mostrarResultadoProcesamiento(data);
                btnCalificarTodos.disabled = false;
            } else {
                showAlert('Error: ' + (data.detail || 'Error al procesar imagen'), 'danger');
            }
            
        } catch (error) {
            hideLoading();
            showAlert('Error de conexión: ' + error.message, 'danger');
        }
    });
    
    // ==============================================
    // CALIFICAR TODOS LOS EXÁMENES
    // ==============================================
    
    btnCalificarTodos.addEventListener('click', async function() {
        if (!confirm('¿Deseas calificar TODOS los exámenes capturados?')) {
            return;
        }
        
        showLoading('Calificando todos los exámenes...');
        
        try {
            const response = await fetch('/api/calificar-todos', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            hideLoading();
            
            if (response.ok) {
                mostrarResultadoCalificacion(data);
            } else {
                showAlert('Error: ' + (data.detail || 'Error al calificar'), 'danger');
            }
            
        } catch (error) {
            hideLoading();
            showAlert('Error de conexión: ' + error.message, 'danger');
        }
    });
    
    // ==============================================
    // VER RESULTADOS
    // ==============================================
    
    btnVerResultados.addEventListener('click', function() {
        window.location.href = '/resultados';
    });
    
    // ==============================================
    // LIMPIAR DEMO
    // ==============================================
    
    btnLimpiar.addEventListener('click', async function() {
        if (!confirm('¿Deseas LIMPIAR todos los datos de la demo? Esta acción no se puede deshacer.')) {
            return;
        }
        
        showLoading('Limpiando datos...');
        
        try {
            const response = await fetch('/api/limpiar-demo', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            hideLoading();
            
            if (response.ok) {
                showAlert('Demo limpiada exitosamente. Recargando página...', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                showAlert('Error: ' + (data.detail || 'Error al limpiar'), 'danger');
            }
            
        } catch (error) {
            hideLoading();
            showAlert('Error de conexión: ' + error.message, 'danger');
        }
    });
    
    // ==============================================
    // FUNCIONES AUXILIARES
    // ==============================================
    
    function mostrarResultadoProcesamiento(data) {
        resultadoCalificacion.style.display = 'block';
        
        let html = `
            <div class="alert alert-success">
                <span style="font-size: 1.5rem;">✅</span>
                <div>
                    <strong>¡Imagen procesada exitosamente!</strong>
                    <p style="margin-top: 0.5rem;">API utilizada: <strong>${data.api_utilizada.toUpperCase()}</strong></p>
                </div>
            </div>
            
            <div class="result-item">
                <span class="result-label">Postulante:</span>
                <span class="result-value">${data.postulante}</span>
            </div>
            
            <div class="result-item">
                <span class="result-label">DNI:</span>
                <span class="result-value">${data.dni}</span>
            </div>
            
            <div class="result-item">
                <span class="result-label">Respuestas detectadas:</span>
                <span class="result-value">${data.respuestas_detectadas}/100</span>
            </div>
            
            <div class="result-item">
                <span class="result-label">Tiempo de procesamiento:</span>
                <span class="result-value">${data.tiempo_procesamiento}s</span>
            </div>
        `;
        
        if (data.nota !== undefined) {
            html += `
                <div class="result-item" style="background: #d1fae5; border: 2px solid #10b981;">
                    <span class="result-label" style="color: #065f46; font-size: 1.2rem;">📊 NOTA FINAL:</span>
                    <span class="result-value" style="color: #065f46; font-size: 1.5rem;">${data.nota}/100</span>
                </div>
            `;
        }
        
        resultadoCalificacion.innerHTML = html;
        
        // Scroll al resultado
        resultadoCalificacion.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    function mostrarResultadoCalificacion(data) {
        resultadoCalificacion.style.display = 'block';
        
        const html = `
            <div class="alert alert-success">
                <span style="font-size: 1.5rem;">🎉</span>
                <div>
                    <strong>¡Calificación completada!</strong>
                    <p style="margin-top: 0.5rem;">Se han calificado ${data.examenes_calificados} exámenes</p>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">${data.examenes_calificados}</div>
                    <div class="stat-label">Exámenes Calificados</div>
                </div>
                
                <div class="stat-card" style="background: linear-gradient(135deg, #10b981, #059669);">
                    <div class="stat-value">${data.nota_promedio}</div>
                    <div class="stat-label">Nota Promedio</div>
                </div>
                
                <div class="stat-card" style="background: linear-gradient(135deg, #f59e0b, #d97706);">
                    <div class="stat-value">${data.nota_maxima}</div>
                    <div class="stat-label">Nota Máxima</div>
                </div>
                
                <div class="stat-card" style="background: linear-gradient(135deg, #ef4444, #dc2626);">
                    <div class="stat-value">${data.nota_minima}</div>
                    <div class="stat-label">Nota Mínima</div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 2rem;">
                <button onclick="window.location.href='/resultados'" class="btn btn-primary btn-large">
                    📊 Ver Ranking Completo
                </button>
            </div>
        `;
        
        resultadoCalificacion.innerHTML = html;
        resultadoCalificacion.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    function showAlert(message, type = 'success') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.style.position = 'fixed';
        alert.style.top = '20px';
        alert.style.right = '20px';
        alert.style.zIndex = '10000';
        alert.style.minWidth = '300px';
        alert.style.animation = 'slideInRight 0.3s ease';
        
        const icon = type === 'success' ? '✅' : 
                     type === 'danger' ? '❌' : 
                     type === 'warning' ? '⚠️' : 'ℹ️';
        
        alert.innerHTML = `
            <span style="font-size: 1.5rem;">${icon}</span>
            <div>${message}</div>
        `;
        
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 4000);
    }
    
    function showLoading(text = 'Procesando...') {
        loadingOverlay.style.display = 'flex';
        loadingOverlay.querySelector('.loading-text').textContent = text;
    }
    
    function hideLoading() {
        loadingOverlay.style.display = 'none';
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }
    
});


async function cargarPostulantes() {
    try {
        const response = await fetch('/api/postulantes');
        const postulantes = await response.json();
        
        const select = document.getElementById('postulante');
        if (!select) return;
        
        // Limpiar opciones
        select.innerHTML = '<option value="">-- Seleccionar postulante --</option>';
        
        // Agregar postulantes
        postulantes.forEach(p => {
            const option = document.createElement('option');
            option.value = p.id;
            option.textContent = `${p.dni} - ${p.nombre_completo}`;
            option.dataset.dni = p.dni;
            option.dataset.codigo = p.codigo_unico;
            select.appendChild(option);
        });
        
        console.log(`✅ Cargados ${postulantes.length} postulantes`);
        
    } catch (error) {
        console.error('❌ Error cargando postulantes:', error);
        const select = document.getElementById('postulante');
        if (select) {
            select.innerHTML = '<option value="">Error al cargar postulantes</option>';
        }
    }
}




// ==============================================
// ANIMACIONES CSS (agregar al final del archivo)
// ==============================================

const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);