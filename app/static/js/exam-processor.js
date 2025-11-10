/* ==============================================
   EXAM PROCESSOR - Lógica principal del sistema
   ============================================== */

// Instancias de cámaras
let cameraExam = null;
let cameraKey = null;

// Estado de la aplicación
const appState = {
    examenesCaptados: 0,
    clavesCargadas: false,
    contadorSesion: 0
};

// ==============================================
// INICIALIZACIÓN
// ==============================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Iniciando sistema de exámenes...');
    
    // Inicializar cámaras
    initializeCameras();
    
    // Configurar event listeners
    setupEventListeners();
    
    // Cargar estadísticas iniciales
    loadStatistics();
    
    // Actualizar estadísticas cada 10 segundos
    setInterval(loadStatistics, 10000);
    
    console.log('✅ Sistema inicializado');
});

// ==============================================
// INICIALIZACIÓN DE CÁMARAS
// ==============================================

function initializeCameras() {
    // Cámara para exámenes de postulantes
    cameraExam = new CameraHandler('video-exam', 'canvas-exam');
    
    // Cámara para clave de respuestas
    cameraKey = new CameraHandler('video-key', 'canvas-key');
}

// ==============================================
// EVENT LISTENERS
// ==============================================

function setupEventListeners() {
    // ========== MÓDULO 1: GENERACIÓN DE HOJAS ==========
    const btnGenerarHojas = document.getElementById('btn-generar-hojas');
    if (btnGenerarHojas) {
        btnGenerarHojas.addEventListener('click', generarHojasRespuestas);
    }
    
    const btnDescargarPDF = document.getElementById('btn-descargar-pdf');
    if (btnDescargarPDF) {
        btnDescargarPDF.addEventListener('click', descargarPDF);
    }
    
    // ========== MÓDULO 2: CAPTURA DE EXÁMENES ==========
    const btnActivarCamaraExam = document.getElementById('btn-activar-camara-exam');
    if (btnActivarCamaraExam) {
        btnActivarCamaraExam.addEventListener('click', activarCamaraExamen);
    }
    
    const btnSwitchCameraExam = document.getElementById('btn-switch-camera-exam');
    if (btnSwitchCameraExam) {
        btnSwitchCameraExam.addEventListener('click', () => cameraExam.switchCamera());
    }
    
    const btnCaptureExam = document.getElementById('btn-capture-exam');
    if (btnCaptureExam) {
        btnCaptureExam.addEventListener('click', capturarExamen);
    }
    
    const btnCloseCameraExam = document.getElementById('btn-close-camera-exam');
    if (btnCloseCameraExam) {
        btnCloseCameraExam.addEventListener('click', cerrarCamaraExamen);
    }
    
    const btnRetryExam = document.getElementById('btn-retry-exam');
    if (btnRetryExam) {
        btnRetryExam.addEventListener('click', reiniciarCapturaExamen);
    }
    
    const btnProcessExam = document.getElementById('btn-process-exam');
    if (btnProcessExam) {
        btnProcessExam.addEventListener('click', procesarExamen);
    }
    
    // ========== MÓDULO 3: CLAVE DE RESPUESTAS ==========
    const btnActivarCamaraKey = document.getElementById('btn-activar-camara-key');
    if (btnActivarCamaraKey) {
        btnActivarCamaraKey.addEventListener('click', activarCamaraClave);
    }
    
    const btnSwitchCameraKey = document.getElementById('btn-switch-camera-key');
    if (btnSwitchCameraKey) {
        btnSwitchCameraKey.addEventListener('click', () => cameraKey.switchCamera());
    }
    
    const btnCaptureKey = document.getElementById('btn-capture-key');
    if (btnCaptureKey) {
        btnCaptureKey.addEventListener('click', capturarClave);
    }
    
    const btnCloseCameraKey = document.getElementById('btn-close-camera-key');
    if (btnCloseCameraKey) {
        btnCloseCameraKey.addEventListener('click', cerrarCamaraClave);
    }
    
    const btnRetryKey = document.getElementById('btn-retry-key');
    if (btnRetryKey) {
        btnRetryKey.addEventListener('click', reiniciarCapturaClave);
    }
    
    const btnProcessKey = document.getElementById('btn-process-key');
    if (btnProcessKey) {
        btnProcessKey.addEventListener('click', procesarClave);
    }
    
    // ========== MÓDULO 4: CALIFICACIÓN ==========
    const btnCalificarTodos = document.getElementById('btn-calificar-todos');
    if (btnCalificarTodos) {
        btnCalificarTodos.addEventListener('click', calificarTodos);
    }
    
    const btnVerResultados = document.getElementById('btn-ver-resultados');
    if (btnVerResultados) {
        btnVerResultados.addEventListener('click', () => {
            window.location.href = '/resultados';
        });
    }
    
    const btnExportarResultados = document.getElementById('btn-exportar-resultados');
    if (btnExportarResultados) {
        btnExportarResultados.addEventListener('click', exportarResultados);
    }
}

// ==============================================
// FUNCIONES DE CÁMARA - EXÁMENES
// ==============================================

async function activarCamaraExamen() {
    try {
        showLoading('Iniciando cámara...');
        
        const success = await cameraExam.initialize();
        
        if (success) {
            // Mostrar sección de cámara
            document.getElementById('camera-section-exam').style.display = 'block';
            document.getElementById('btn-activar-camara-exam').style.display = 'none';
            
            showSuccess('Cámara activada correctamente');
        }
        
        hideLoading();
        
    } catch (error) {
        hideLoading();
        showError('No se pudo activar la cámara: ' + error.message);
    }
}

function capturarExamen() {
    const imageData = cameraExam.captureImage();
    
    if (imageData) {
        // Mostrar preview
        document.getElementById('preview-img-exam').src = imageData;
        document.getElementById('preview-exam').style.display = 'block';
        
        // Ocultar cámara
        document.getElementById('camera-section-exam').style.display = 'none';
        
        showSuccess('Imagen capturada. Revisa la foto antes de procesar.');
    }
}

function cerrarCamaraExamen() {
    cameraExam.stopCamera();
    document.getElementById('camera-section-exam').style.display = 'none';
    document.getElementById('btn-activar-camara-exam').style.display = 'block';
}

function reiniciarCapturaExamen() {
    document.getElementById('preview-exam').style.display = 'none';
    document.getElementById('camera-section-exam').style.display = 'block';
}

async function procesarExamen() {
    try {
        showLoading('Procesando examen con Vision API...', 'Extrayendo código y respuestas...');
        
        // Obtener imagen
        const imageBlob = await cameraExam.captureImageBlob();
        
        if (!imageBlob) {
            throw new Error('No se pudo obtener la imagen');
        }
        
        // Crear FormData
        const formData = new FormData();
        formData.append('imagen', imageBlob, 'examen.jpg');
        
        // Enviar al backend
        const response = await fetch('/api/procesar-examen', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        hideLoading();
        
        if (response.ok) {
            mostrarResultadoExamen(result);
            appState.contadorSesion++;
            updateSessionCounter();
            loadStatistics();
            
            // Habilitar botón de clave si hay suficientes exámenes
            if (appState.examenesCaptados >= 10) {
                document.getElementById('btn-activar-camara-key').disabled = false;
            }
        } else {
            showError('Error al procesar: ' + (result.detail || result.error));
        }
        
    } catch (error) {
        hideLoading();
        showError('Error procesando examen: ' + error.message);
    }
}

// ==============================================
// FUNCIONES DE CÁMARA - CLAVE
// ==============================================

async function activarCamaraClave() {
    try {
        // Confirmar acción crítica
        const confirmacion = confirm(
            '⚠️ ATENCIÓN\n\n' +
            'Está a punto de iniciar el proceso de APERTURA DEL SOBRE LACRADO.\n\n' +
            'Este proceso debe ser realizado únicamente por el Director/Decano ' +
            'en presencia de autoridades y veedores.\n\n' +
            '¿Desea continuar?'
        );
        
        if (!confirmacion) return;
        
        showLoading('Iniciando cámara para clave...');
        
        const success = await cameraKey.initialize();
        
        if (success) {
            document.getElementById('camera-section-key').style.display = 'block';
            document.getElementById('btn-activar-camara-key').style.display = 'none';
            
            showSuccess('Cámara activada. Proceda con la apertura del sobre.');
        }
        
        hideLoading();
        
    } catch (error) {
        hideLoading();
        showError('No se pudo activar la cámara: ' + error.message);
    }
}

function capturarClave() {
    const imageData = cameraKey.captureImage();
    
    if (imageData) {
        document.getElementById('preview-img-key').src = imageData;
        document.getElementById('preview-key').style.display = 'block';
        document.getElementById('camera-section-key').style.display = 'none';
        
        showSuccess('Clave capturada. Verifique la imagen antes de procesar.');
    }
}

function cerrarCamaraClave() {
    cameraKey.stopCamera();
    document.getElementById('camera-section-key').style.display = 'none';
    document.getElementById('btn-activar-camara-key').style.display = 'block';
}

function reiniciarCapturaClave() {
    document.getElementById('preview-key').style.display = 'none';
    document.getElementById('camera-section-key').style.display = 'block';
}

async function procesarClave() {
    try {
        // Confirmación adicional
        const confirmacion = confirm(
            '⚠️ CONFIRMACIÓN FINAL\n\n' +
            'Va a procesar la CLAVE DE RESPUESTAS OFICIALES.\n\n' +
            'Una vez procesada, se habilitará la calificación automática.\n\n' +
            '¿Confirma que la imagen es correcta?'
        );
        
        if (!confirmacion) return;
        
        showLoading('Procesando clave oficial...', 'Extrayendo 100 respuestas correctas...');
        
        const imageBlob = await cameraKey.captureImageBlob();
        
        if (!imageBlob) {
            throw new Error('No se pudo obtener la imagen');
        }
        
        const formData = new FormData();
        formData.append('imagen', imageBlob, 'clave.jpg');
        
        const response = await fetch('/api/procesar-clave', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        hideLoading();
        
        if (response.ok) {
            mostrarResultadoClave(result);
            appState.clavesCargadas = true;
            loadStatistics();
            
            // Habilitar botón de calificar
            document.getElementById('btn-calificar-todos').disabled = false;
            document.getElementById('req-clave').innerHTML = '✅ Clave de respuestas correctas cargada';
        } else {
            showError('Error al procesar clave: ' + (result.detail || result.error));
        }
        
    } catch (error) {
        hideLoading();
        showError('Error procesando clave: ' + error.message);
    }
}

// ==============================================
// GENERACIÓN DE HOJAS
// ==============================================

async function generarHojasRespuestas() {
    try {
        showLoading('Generando hojas de respuestas...', 'Esto puede tomar unos segundos...');
        
        const response = await fetch('/api/generar-hojas', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        hideLoading();
        
        if (response.ok) {
            showSuccess(`✅ Se generaron ${result.hojas_generadas} hojas de respuestas`);
            document.getElementById('btn-descargar-pdf').disabled = false;
        } else {
            showError('Error generando hojas: ' + result.detail);
        }
        
    } catch (error) {
        hideLoading();
        showError('Error: ' + error.message);
    }
}

async function descargarPDF() {
    window.location.href = '/api/descargar-hojas-pdf';
}

// ==============================================
// CALIFICACIÓN
// ==============================================

async function calificarTodos() {
    try {
        const confirmacion = confirm(
            '🚀 CALIFICACIÓN AUTOMÁTICA\n\n' +
            'Se van a calificar todos los exámenes capturados comparándolos ' +
            'con la clave de respuestas correctas.\n\n' +
            'Este proceso es irreversible.\n\n' +
            '¿Desea continuar?'
        );
        
        if (!confirmacion) return;
        
        showLoading('Calificando todos los exámenes...', 'Comparando respuestas...');
        
        const response = await fetch('/api/calificar-todos', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        hideLoading();
        
        if (response.ok) {
            mostrarResultadoCalificacion(result);
            document.getElementById('btn-exportar-resultados').disabled = false;
        } else {
            showError('Error en calificación: ' + result.detail);
        }
        
    } catch (error) {
        hideLoading();
        showError('Error: ' + error.message);
    }
}

async function exportarResultados() {
    window.location.href = '/api/exportar-resultados-excel';
}

// ==============================================
// ESTADÍSTICAS
// ==============================================

async function loadStatistics() {
    try {
        const response = await fetch('/api/estadisticas');
        const stats = await response.json();
        
        // Actualizar DOM
        document.getElementById('total-postulantes').textContent = stats.total_postulantes || 0;
        document.getElementById('examenes-capturados').textContent = stats.examenes_capturados || 0;
        document.getElementById('examenes-calificados').textContent = stats.examenes_calificados || 0;
        document.getElementById('clave-estado').textContent = stats.clave_cargada ? '✅' : '❌';
        
        // Actualizar estado global
        appState.examenesCaptados = stats.examenes_capturados || 0;
        
        // Actualizar requisitos
        if (stats.examenes_capturados > 0) {
            document.getElementById('req-examenes').innerHTML = '✅ Exámenes de postulantes capturados';
        }
        
        if (stats.clave_cargada) {
            document.getElementById('req-clave').innerHTML = '✅ Clave de respuestas correctas cargada';
        }
        
    } catch (error) {
        console.error('Error cargando estadísticas:', error);
    }
}

function updateSessionCounter() {
    document.getElementById('contador-sesion').textContent = appState.contadorSesion;
}

// ==============================================
// MOSTRAR RESULTADOS
// ==============================================

function mostrarResultadoExamen(data) {
    const container = document.getElementById('resultado-examen');
    container.innerHTML = `
        <div style="background: #f0fdf4; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #059669;">
            <h3 style="color: #059669; margin-bottom: 1rem;">✅ Examen Procesado Exitosamente</h3>
            <div style="display: grid; gap: 0.75rem;">
                <p><strong>Código extraído:</strong> ${data.codigo || 'N/A'}</p>
                <p><strong>DNI Postulante:</strong> ${data.dni_postulante || 'N/A'}</p>
                <p><strong>Código Aula:</strong> ${data.codigo_aula || 'N/A'}</p>
                <p><strong>DNI Profesor:</strong> ${data.dni_profesor || 'N/A'}</p>
                <p><strong>Respuestas detectadas:</strong> ${data.respuestas_detectadas}/100</p>
                <p><strong>API utilizada:</strong> ${data.api_utilizada || 'N/A'}</p>
                <p><strong>Tiempo:</strong> ${data.tiempo_procesamiento}s</p>
            </div>
        </div>
    `;
    container.style.display = 'block';
    
    // Limpiar preview
    document.getElementById('preview-exam').style.display = 'none';
    document.getElementById('btn-activar-camara-exam').style.display = 'block';
}

function mostrarResultadoClave(data) {
    const container = document.getElementById('resultado-clave');
    container.innerHTML = `
        <div style="background: #fef2f2; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #dc2626;">
            <h3 style="color: #dc2626; margin-bottom: 1rem;">🔐 Clave Oficial Cargada</h3>
            <div style="display: grid; gap: 0.75rem;">
                <p><strong>Respuestas correctas extraídas:</strong> ${data.respuestas_cargadas}/100</p>
                <p><strong>API utilizada:</strong> ${data.api_utilizada}</p>
                <p><strong>Tiempo:</strong> ${data.tiempo_procesamiento}s</p>
                <p style="margin-top: 1rem; padding: 1rem; background: #fee2e2; border-radius: 6px;">
                    <strong>⚠️ El sistema está listo para calificar automáticamente.</strong>
                </p>
            </div>
        </div>
    `;
    container.style.display = 'block';
    
    document.getElementById('preview-key').style.display = 'none';
    document.getElementById('btn-activar-camara-key').style.display = 'block';
}

function mostrarResultadoCalificacion(data) {
    const container = document.getElementById('resultado-calificacion');
    container.innerHTML = `
        <div style="text-align: center;">
            <h2 style="color: #059669; margin-bottom: 1.5rem;">🎉 Calificación Completada</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
                <div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 2.5rem; font-weight: 700; color: #059669;">${data.examenes_calificados}</div>
                    <div style="color: #6b7280; margin-top: 0.5rem;">Exámenes Calificados</div>
                </div>
                <div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 2.5rem; font-weight: 700; color: #1e3a8a;">${data.nota_promedio}</div>
                    <div style="color: #6b7280; margin-top: 0.5rem;">Nota Promedio</div>
                </div>
                <div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 2.5rem; font-weight: 700; color: #d97706;">${data.nota_maxima}</div>
                    <div style="color: #6b7280; margin-top: 0.5rem;">Nota Máxima</div>
                </div>
                <div style="background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 2.5rem; font-weight: 700; color: #dc2626;">${data.nota_minima}</div>
                    <div style="color: #6b7280; margin-top: 0.5rem;">Nota Mínima</div>
                </div>
            </div>
            <button onclick="window.location.href='/resultados'" class="btn-formal-large btn-primary-large" style="margin-top: 1rem;">
                <span class="btn-icon-large">🏆</span>
                <span>VER RANKING COMPLETO</span>
            </button>
        </div>
    `;
    container.style.display = 'block';
}

// ==============================================
// UTILIDADES UI
// ==============================================

function showLoading(message, submessage = 'Por favor espere') {
    const overlay = document.getElementById('loading-overlay-formal');
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-subtext').textContent = submessage;
    overlay.style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay-formal').style.display = 'none';
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error');
}

function showToast(message, type = 'info') {
    const colors = {
        success: { bg: '#059669', icon: '✅' },
        error: { bg: '#dc2626', icon: '❌' },
        warning: { bg: '#f59e0b', icon: '⚠️' },
        info: { bg: '#1e3a8a', icon: 'ℹ️' }
    };
    
    const config = colors[type] || colors.info;
    
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${config.bg};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        z-index: 10000;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        max-width: 400px;
        animation: slideIn 0.3s ease;
    `;
    
    toast.innerHTML = `
        <span style="font-size: 1.5rem;">${config.icon}</span>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}