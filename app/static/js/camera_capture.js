// ==========================================
// POSTULANDO - Sistema de Captura Profesional
// Cámara para Profesor y Director/Decano
// ==========================================

class SistemaCaptura {
    constructor() {
        // Cámara Profesor
        this.streamProfesor = null;
        this.videoProfesor = null;
        this.photoProfesor = null;
        
        // Cámara Director
        this.streamDirector = null;
        this.videoDirector = null;
        this.photoDirector = null;
        
        // Canvas para capturas
        this.canvas = document.createElement('canvas');
        
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.setupEventListeners();
            this.setupTabs();
        });
    }

    setupEventListeners() {
        // ========== PROFESOR ==========
        const btnStartProf = document.getElementById('btn-start-camera');
        if (btnStartProf) {
            btnStartProf.addEventListener('click', () => this.iniciarCameraProfesor());
        }

        const btnCaptureProf = document.getElementById('btn-capture');
        if (btnCaptureProf) {
            btnCaptureProf.addEventListener('click', () => this.capturarProfesor());
        }

        const btnRetakeProf = document.getElementById('btn-retake');
        if (btnRetakeProf) {
            btnRetakeProf.addEventListener('click', () => this.retomarProfesor());
        }

        const btnConfirmProf = document.getElementById('btn-confirm');
        if (btnConfirmProf) {
            btnConfirmProf.addEventListener('click', () => this.procesarExamenProfesor());
        }

        // ========== DIRECTOR ==========
        const btnStartDir = document.getElementById('btn-start-camera-clave');
        if (btnStartDir) {
            btnStartDir.addEventListener('click', () => this.iniciarCameraDirector());
        }

        const btnCaptureDir = document.getElementById('btn-capture-clave');
        if (btnCaptureDir) {
            btnCaptureDir.addEventListener('click', () => this.capturarDirector());
        }

        const btnRetakeDir = document.getElementById('btn-retake-clave');
        if (btnRetakeDir) {
            btnRetakeDir.addEventListener('click', () => this.retomarDirector());
        }

        const btnConfirmDir = document.getElementById('btn-confirm-clave');
        if (btnConfirmDir) {
            btnConfirmDir.addEventListener('click', () => this.procesarClaveDirector());
        }
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        tabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.cambiarTab(tab);
            });
        });
    }

    cambiarTab(tabName) {
        // Actualizar botones
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`)?.classList.add('active');

        // Actualizar contenido
        document.getElementById('tab-profesor')?.classList.add('hidden');
        document.getElementById('tab-director')?.classList.add('hidden');
        document.getElementById('tab-resultados')?.classList.add('hidden');
        
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
        
        // Detener cámaras al cambiar de tab
        this.detenerTodasLasCamaras();
    }

    // ==========================================
    // FUNCIONES PROFESOR
    // ==========================================

    async iniciarCameraProfesor() {
        try {
            const constraints = {
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };

            this.streamProfesor = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoProfesor = document.getElementById('camera-video');
            
            if (!this.videoProfesor) {
                throw new Error('Elemento video no encontrado');
            }

            this.videoProfesor.srcObject = this.streamProfesor;
            await this.videoProfesor.play();

            // Mostrar controles
            document.getElementById('btn-start-wrapper')?.classList.add('hidden');
            document.getElementById('camera-controls')?.classList.remove('hidden');

            this.notificar('Cámara activada correctamente', 'success');

        } catch (error) {
            console.error('Error al acceder a la cámara:', error);
            this.notificar('No se pudo acceder a la cámara. Verifica los permisos.', 'danger');
        }
    }

    capturarProfesor() {
        if (!this.videoProfesor || !this.streamProfesor) {
            this.notificar('Primero activa la cámara', 'warning');
            return;
        }

        // Capturar frame
        this.canvas.width = this.videoProfesor.videoWidth;
        this.canvas.height = this.videoProfesor.videoHeight;
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.videoProfesor, 0, 0);
        this.photoProfesor = this.canvas.toDataURL('image/jpeg', 0.95);

        // Mostrar preview
        const preview = document.getElementById('preview-image');
        if (preview) preview.src = this.photoProfesor;

        document.getElementById('camera-container')?.classList.add('hidden');
        document.getElementById('preview-container')?.classList.remove('hidden');

        this.detenerCamera(this.streamProfesor);
        this.streamProfesor = null;

        this.efectoFlash();
        this.notificar('Foto capturada', 'success');
    }

    retomarProfesor() {
        this.photoProfesor = null;
        document.getElementById('preview-container')?.classList.add('hidden');
        document.getElementById('camera-container')?.classList.remove('hidden');
        this.iniciarCameraProfesor();
    }

    async procesarExamenProfesor() {
        if (!this.photoProfesor) {
            this.notificar('No hay foto para procesar', 'warning');
            return;
        }

        this.mostrarLoading('Procesando examen...');

        try {
            const apiVision = document.getElementById('api-vision')?.value || 'google';
            
            const response = await fetch('/api/procesar-examen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    imagen: this.photoProfesor,
                    api_vision: apiVision,
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) throw new Error('Error en el servidor');

            const resultado = await response.json();
            this.mostrarResultado(resultado, 'result-container');
            this.actualizarEstadisticas();
            
            // Limpiar para siguiente captura
            setTimeout(() => {
                this.retomarProfesor();
                document.getElementById('result-container')?.classList.add('hidden');
            }, 5000);

        } catch (error) {
            console.error('Error:', error);
            this.notificar('Error al procesar el examen', 'danger');
        } finally {
            this.ocultarLoading();
        }
    }

    // ==========================================
    // FUNCIONES DIRECTOR
    // ==========================================

    async iniciarCameraDirector() {
        try {
            const constraints = {
                video: {
                    facingMode: 'environment',
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };

            this.streamDirector = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoDirector = document.getElementById('camera-video-clave');
            
            if (!this.videoDirector) {
                throw new Error('Elemento video no encontrado');
            }

            this.videoDirector.srcObject = this.streamDirector;
            await this.videoDirector.play();

            // Mostrar controles
            document.getElementById('btn-start-wrapper-clave')?.classList.add('hidden');
            document.getElementById('camera-controls-clave')?.classList.remove('hidden');

            this.notificar('Cámara activada para captura de clave', 'success');

        } catch (error) {
            console.error('Error al acceder a la cámara:', error);
            this.notificar('No se pudo acceder a la cámara', 'danger');
        }
    }

    capturarDirector() {
        if (!this.videoDirector || !this.streamDirector) {
            this.notificar('Primero activa la cámara', 'warning');
            return;
        }

        // Capturar frame
        this.canvas.width = this.videoDirector.videoWidth;
        this.canvas.height = this.videoDirector.videoHeight;
        const ctx = this.canvas.getContext('2d');
        ctx.drawImage(this.videoDirector, 0, 0);
        this.photoDirector = this.canvas.toDataURL('image/jpeg', 0.95);

        // Mostrar preview
        const preview = document.getElementById('preview-image-clave');
        if (preview) preview.src = this.photoDirector;

        document.getElementById('camera-container-clave')?.classList.add('hidden');
        document.getElementById('preview-container-clave')?.classList.remove('hidden');

        this.detenerCamera(this.streamDirector);
        this.streamDirector = null;

        this.efectoFlash();
        this.notificar('Clave capturada', 'success');
    }

    retomarDirector() {
        this.photoDirector = null;
        document.getElementById('preview-container-clave')?.classList.add('hidden');
        document.getElementById('camera-container-clave')?.classList.remove('hidden');
        this.iniciarCameraDirector();
    }

    async procesarClaveDirector() {
        if (!this.photoDirector) {
            this.notificar('No hay foto de clave para procesar', 'warning');
            return;
        }

        this.mostrarLoading('Procesando clave de respuestas...');

        try {
            const apiVision = document.getElementById('api-vision-clave')?.value || 'google';
            
            const response = await fetch('/api/procesar-clave', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    imagen: this.photoDirector,
                    api_vision: apiVision,
                    cargado_por: 'Director/Decano',
                    timestamp: new Date().toISOString()
                })
            });

            if (!response.ok) throw new Error('Error en el servidor');

            const resultado = await response.json();
            this.mostrarResultado(resultado, 'result-container-clave');
            
            // Actualizar estado de clave cargada
            const claveEstado = document.getElementById('clave-estado');
            if (claveEstado) {
                claveEstado.textContent = 'Sí';
                claveEstado.style.color = '#10b981';
            }

            this.notificar('Clave procesada. Iniciando calificación automática...', 'success');

        } catch (error) {
            console.error('Error:', error);
            this.notificar('Error al procesar la clave', 'danger');
        } finally {
            this.ocultarLoading();
        }
    }

    // ==========================================
    // UTILIDADES
    // ==========================================

    detenerCamera(stream) {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
    }

    detenerTodasLasCamaras() {
        this.detenerCamera(this.streamProfesor);
        this.detenerCamera(this.streamDirector);
        this.streamProfesor = null;
        this.streamDirector = null;
    }

    efectoFlash() {
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            inset: 0;
            background: white;
            z-index: 9999;
            animation: flash 0.3s ease;
            pointer-events: none;
        `;
        document.body.appendChild(flash);
        setTimeout(() => flash.remove(), 300);
    }

    mostrarResultado(resultado, containerId) {
        const html = `
            <div class="alert alert-success">
                <svg style="width: 20px; height: 20px;"><path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19L21 7l-1.41-1.41z"/></svg>
                <div>
                    <strong>Procesado exitosamente</strong>
                    <p style="margin: 0.5rem 0 0 0; font-size: 0.875rem;">
                        ${resultado.mensaje || 'Operación completada'}
                    </p>
                </div>
            </div>
        `;
        
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = html;
            container.classList.remove('hidden');
        }
    }

    async actualizarEstadisticas() {
        try {
            const response = await fetch('/api/estadisticas');
            const stats = await response.json();
            
            if (stats.examenes_capturados !== undefined) {
                const elem = document.getElementById('examenes-capturados');
                if (elem) elem.textContent = stats.examenes_capturados;
            }
            
            if (stats.examenes_calificados !== undefined) {
                const elem = document.getElementById('examenes-calificados');
                if (elem) elem.textContent = stats.examenes_calificados;
            }
        } catch (error) {
            console.error('Error actualizando estadísticas:', error);
        }
    }

    mostrarLoading(mensaje = 'Procesando...') {
        const html = `
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem; color: white;">
                <div style="width: 60px; height: 60px; border: 6px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <p style="font-weight: 600;">${mensaje}</p>
            </div>
        `;
        
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.cssText = `
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.85);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        `;
        overlay.innerHTML = html;
        document.body.appendChild(overlay);
    }

    ocultarLoading() {
        document.getElementById('loading-overlay')?.remove();
    }

    notificar(mensaje, tipo = 'info') {
        const colores = {
            info: '#3b82f6',
            success: '#10b981',
            warning: '#f59e0b',
            danger: '#ef4444'
        };

        const notif = document.createElement('div');
        notif.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            padding: 1rem 1.5rem;
            background: white;
            border-left: 4px solid ${colores[tipo]};
            border-radius: 12px;
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            z-index: 9999;
            max-width: 400px;
            animation: slideIn 0.3s ease;
            font-size: 0.9375rem;
            font-weight: 500;
        `;
        notif.textContent = mensaje;
        document.body.appendChild(notif);

        setTimeout(() => {
            notif.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notif.remove(), 300);
        }, 4000);
    }
}

// CSS Animations
const style = document.createElement('style');
style.textContent = `
    @keyframes flash {
        0%, 100% { opacity: 0; }
        50% { opacity: 1; }
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Inicializar
const app = new SistemaCaptura();

// Verificar soporte de cámara
if (!navigator.mediaDevices?.getUserMedia) {
    alert('Tu navegador no soporta acceso a la cámara. Usa Chrome, Firefox o Safari.');
}