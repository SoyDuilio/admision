// ==========================================
// POSTULANDO - JavaScript Profesional v3.0
// Acceso Real a Cámara del Dispositivo
// ==========================================

class CapturaExamenes {
    constructor() {
        this.stream = null;
        this.videoElement = null;
        this.canvas = null;
        this.photoData = null;
        this.init();
    }

    init() {
        // Inicializar al cargar DOM
        document.addEventListener('DOMContentLoaded', () => {
            this.setupEventListeners();
            this.setupCanvas();
        });
    }

    setupEventListeners() {
        // Botón para iniciar cámara
        const btnIniciarCamara = document.getElementById('btn-iniciar-camara');
        if (btnIniciarCamara) {
            btnIniciarCamara.addEventListener('click', () => this.iniciarCamara());
        }

        // Botón para capturar foto
        const btnCapturar = document.getElementById('btn-capturar');
        if (btnCapturar) {
            btnCapturar.addEventListener('click', () => this.capturarFoto());
        }

        // Botón para retomar foto
        const btnRetomar = document.getElementById('btn-retomar');
        if (btnRetomar) {
            btnRetomar.addEventListener('click', () => this.retomar());
        }

        // Botón para confirmar y procesar
        const btnProcesar = document.getElementById('btn-procesar');
        if (btnProcesar) {
            btnProcesar.addEventListener('click', () => this.procesarExamen());
        }

        // Pestañas
        const tabButtons = document.querySelectorAll('.tab-button');
        tabButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                this.cambiarTab(e.target.dataset.tab);
            });
        });
    }

    setupCanvas() {
        // Crear canvas para capturar fotos
        this.canvas = document.createElement('canvas');
    }

    async iniciarCamara() {
        try {
            // Solicitar permiso de cámara
            const constraints = {
                video: {
                    facingMode: 'environment', // Cámara trasera en móviles
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Obtener elemento video
            this.videoElement = document.getElementById('camera-video');
            if (!this.videoElement) {
                throw new Error('Elemento video no encontrado');
            }

            // Asignar stream al video
            this.videoElement.srcObject = this.stream;
            await this.videoElement.play();

            // Mostrar controles de cámara
            this.mostrarControlesCamara();
            this.mostrarNotificacion('Cámara activada', 'success');

        } catch (error) {
            console.error('Error al acceder a la cámara:', error);
            this.mostrarNotificacion(
                'No se pudo acceder a la cámara. Verifica los permisos.',
                'danger'
            );
        }
    }

    capturarFoto() {
        if (!this.videoElement || !this.stream) {
            this.mostrarNotificacion('Primero debes iniciar la cámara', 'warning');
            return;
        }

        // Configurar canvas con dimensiones del video
        this.canvas.width = this.videoElement.videoWidth;
        this.canvas.height = this.videoElement.videoHeight;

        // Capturar frame actual
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.videoElement, 0, 0);

        // Convertir a base64
        this.photoData = this.canvas.toDataURL('image/jpeg', 0.95);

        // Mostrar preview
        this.mostrarPreview();
        
        // Detener cámara
        this.detenerCamara();

        // Efecto de flash
        this.efectoFlash();

        this.mostrarNotificacion('Foto capturada correctamente', 'success');
    }

    mostrarPreview() {
        // Ocultar cámara, mostrar preview
        const cameraContainer = document.getElementById('camera-container');
        const previewContainer = document.getElementById('preview-container');
        const previewImage = document.getElementById('preview-image');

        if (cameraContainer) cameraContainer.classList.add('hidden');
        if (previewContainer) previewContainer.classList.remove('hidden');
        if (previewImage) previewImage.src = this.photoData;

        // Mostrar botones de acción
        this.mostrarBotonesAccion();
    }

    retomar() {
        // Limpiar foto
        this.photoData = null;

        // Ocultar preview
        const previewContainer = document.getElementById('preview-container');
        if (previewContainer) previewContainer.classList.add('hidden');

        // Reiniciar cámara
        this.iniciarCamara();
    }

    async procesarExamen() {
        if (!this.photoData) {
            this.mostrarNotificacion('No hay foto para procesar', 'warning');
            return;
        }

        // Mostrar loading
        this.mostrarLoading();

        try {
            // Aquí va la integración con tu backend
            const apiVision = document.getElementById('api-vision')?.value || 'google';
            
            const response = await fetch('/api/procesar-examen', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    imagen: this.photoData,
                    api_vision: apiVision,
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) {
                throw new Error('Error al procesar examen');
            }

            const resultado = await response.json();

            // Mostrar resultado
            this.mostrarResultado(resultado);
            
            // Reiniciar para siguiente captura
            this.reiniciar();

        } catch (error) {
            console.error('Error al procesar examen:', error);
            this.mostrarNotificacion(
                'Error al procesar el examen. Intenta nuevamente.',
                'danger'
            );
        } finally {
            this.ocultarLoading();
        }
    }

    detenerCamara() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
    }

    reiniciar() {
        this.photoData = null;
        this.detenerCamara();
        
        // Ocultar preview
        const previewContainer = document.getElementById('preview-container');
        if (previewContainer) previewContainer.classList.add('hidden');
        
        // Mostrar botón de iniciar cámara
        const cameraContainer = document.getElementById('camera-container');
        if (cameraContainer) cameraContainer.classList.remove('hidden');
    }

    mostrarControlesCamara() {
        const btnIniciar = document.getElementById('btn-iniciar-camara');
        const controls = document.getElementById('camera-controls');
        
        if (btnIniciar) btnIniciar.classList.add('hidden');
        if (controls) controls.classList.remove('hidden');
    }

    mostrarBotonesAccion() {
        const btnRetomar = document.getElementById('btn-retomar');
        const btnProcesar = document.getElementById('btn-procesar');
        
        if (btnRetomar) btnRetomar.classList.remove('hidden');
        if (btnProcesar) btnProcesar.classList.remove('hidden');
    }

    efectoFlash() {
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: white;
            z-index: 9999;
            animation: flash 0.3s ease;
            pointer-events: none;
        `;
        
        document.body.appendChild(flash);
        
        setTimeout(() => flash.remove(), 300);
    }

    cambiarTab(tabName) {
        // Actualizar botones
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.querySelector(`[data-tab="${tabName}"]`);
        if (activeBtn) activeBtn.classList.add('active');

        // Actualizar contenido
        document.querySelectorAll('[id^="tab-"]').forEach(content => {
            content.classList.add('hidden');
        });
        const activeContent = document.getElementById(`tab-${tabName}`);
        if (activeContent) activeContent.classList.remove('hidden');
    }

    mostrarResultado(resultado) {
        const resultadoHTML = `
            <div class="alert alert-success">
                <span class="alert-icon">✅</span>
                <div>
                    <strong>Examen procesado exitosamente</strong>
                    <p>Códigos verificados: ${resultado.codigos_verificados || 'N/A'}</p>
                    <p>Respuestas detectadas: ${resultado.respuestas_detectadas || 0}/100</p>
                </div>
            </div>
        `;
        
        const container = document.getElementById('resultado-container');
        if (container) {
            container.innerHTML = resultadoHTML;
            container.classList.remove('hidden');
        }
    }

    mostrarLoading() {
        const loadingHTML = `
            <div class="loading-overlay">
                <div class="loading-spinner"></div>
                <p>Procesando examen...</p>
            </div>
        `;
        
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.innerHTML = loadingHTML;
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            color: white;
        `;
        
        document.body.appendChild(overlay);
    }

    ocultarLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.remove();
    }

    mostrarNotificacion(mensaje, tipo = 'info') {
        const iconos = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'danger': '❌'
        };

        const notificacion = document.createElement('div');
        notificacion.className = `alert alert-${tipo}`;
        notificacion.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            max-width: 500px;
            animation: slideIn 0.3s ease;
        `;
        notificacion.innerHTML = `
            <span class="alert-icon">${iconos[tipo]}</span>
            <span>${mensaje}</span>
        `;

        document.body.appendChild(notificacion);

        setTimeout(() => {
            notificacion.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notificacion.remove(), 300);
        }, 4000);
    }
}

// CSS adicional para animaciones
const style = document.createElement('style');
style.textContent = `
    @keyframes flash {
        0% { opacity: 0; }
        50% { opacity: 1; }
        100% { opacity: 0; }
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .loading-spinner {
        width: 60px;
        height: 60px;
        border: 6px solid rgba(255, 255, 255, 0.3);
        border-top-color: white;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 1rem;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Inicializar aplicación
const app = new CapturaExamenes();

// Detectar capacidades del dispositivo
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    console.error('Tu navegador no soporta acceso a la cámara');
    alert('Tu navegador no soporta acceso a la cámara. Usa Chrome, Firefox o Safari actualizado.');
}