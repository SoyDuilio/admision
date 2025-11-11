// ==========================================
// POSTULANDO - Sistema de Captura de Cámara
// Versión Unificada y Profesional
// ==========================================

class CameraCapture {
    constructor(containerId, options = {}) {
        // Contenedor principal
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container con id "${containerId}" no encontrado`);
        }

        // Configuración
        this.config = {
            // Video constraints
            width: options.width || 1920,
            height: options.height || 1440,
            facingMode: options.facingMode || 'environment', // 'environment' = posterior, 'user' = frontal
            
            // Calidad de imagen
            imageQuality: options.imageQuality || 0.85,
            imageFormat: options.imageFormat || 'image/jpeg',
            
            // Callbacks
            onPhotoTaken: options.onPhotoTaken || null,
            onError: options.onError || null,
            onCameraReady: options.onCameraReady || null,
            
            // Textos personalizables
            texts: {
                capture: options.texts?.capture || 'Capturar Foto',
                retake: options.texts?.retake || 'Tomar Otra',
                confirm: options.texts?.confirm || 'Confirmar y Procesar',
                switchCamera: options.texts?.switchCamera || 'Cambiar Cámara',
                loading: options.texts?.loading || 'Procesando...'
            }
        };

        // Estado
        this.stream = null;
        this.photoBlob = null;
        this.photoDataUrl = null;
        this.currentFacingMode = this.config.facingMode;

        // Elementos DOM
        this.elements = {};

        // Inicializar
        this.init();
    }

    init() {
        this.createUI();
        this.attachEvents();
    }

    createUI() {
        this.container.innerHTML = `
            <div class="camera-container">
                <!-- Video en vivo -->
                <div class="camera-view" id="cameraView">
                    <video id="cameraVideo" autoplay playsinline></video>
                    <div class="camera-overlay">
                        <div class="camera-frame"></div>
                        <p class="camera-hint">Coloque la hoja de respuestas dentro del marco</p>
                    </div>
                </div>

                <!-- Preview de foto capturada -->
                <div class="photo-preview" id="photoPreview" style="display: none;">
                    <img id="photoImage" alt="Foto capturada">
                    <div class="photo-overlay">
                        <div class="photo-info">
                            <span id="photoSize"></span>
                            <span id="photoResolution"></span>
                        </div>
                    </div>
                </div>

                <!-- Canvas oculto para procesamiento -->
                <canvas id="photoCanvas" style="display: none;"></canvas>

                <!-- Controles -->
                <div class="camera-controls">
                    <!-- Controles cuando está en modo video -->
                    <div class="controls-video" id="controlsVideo">
                        <button type="button" class="btn-camera btn-switch" id="btnSwitch" title="Cambiar cámara">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M17 3l4 4-4 4"/>
                                <path d="M3 11V9a4 4 0 0 1 4-4h14"/>
                                <path d="M7 21l-4-4 4-4"/>
                                <path d="M21 13v2a4 4 0 0 1-4 4H3"/>
                            </svg>
                            <span>${this.config.texts.switchCamera}</span>
                        </button>
                        
                        <button type="button" class="btn-camera btn-capture" id="btnCapture">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="10"/>
                                <circle cx="12" cy="12" r="6" fill="currentColor"/>
                            </svg>
                            <span>${this.config.texts.capture}</span>
                        </button>
                    </div>

                    <!-- Controles cuando hay foto capturada -->
                    <div class="controls-photo" id="controlsPhoto" style="display: none;">
                        <button type="button" class="btn-camera btn-retake" id="btnRetake">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="1 4 1 10 7 10"/>
                                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                            </svg>
                            <span>${this.config.texts.retake}</span>
                        </button>
                        
                        <button type="button" class="btn-camera btn-confirm" id="btnConfirm">
                            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                            <span>${this.config.texts.confirm}</span>
                        </button>
                    </div>

                    <!-- Estado de carga -->
                    <div class="loading-state" id="loadingState" style="display: none;">
                        <div class="spinner"></div>
                        <p>${this.config.texts.loading}</p>
                    </div>
                </div>

                <!-- Información técnica (solo en desarrollo) -->
                <div class="camera-info" id="cameraInfo" style="display: none;">
                    <div class="info-item">
                        <span>Cámara:</span>
                        <span id="infoCamera">-</span>
                    </div>
                    <div class="info-item">
                        <span>Resolución:</span>
                        <span id="infoResolution">-</span>
                    </div>
                </div>
            </div>
        `;

        // Guardar referencias a elementos
        this.elements = {
            video: document.getElementById('cameraVideo'),
            canvas: document.getElementById('photoCanvas'),
            cameraView: document.getElementById('cameraView'),
            photoPreview: document.getElementById('photoPreview'),
            photoImage: document.getElementById('photoImage'),
            photoSize: document.getElementById('photoSize'),
            photoResolution: document.getElementById('photoResolution'),
            controlsVideo: document.getElementById('controlsVideo'),
            controlsPhoto: document.getElementById('controlsPhoto'),
            loadingState: document.getElementById('loadingState'),
            btnCapture: document.getElementById('btnCapture'),
            btnRetake: document.getElementById('btnRetake'),
            btnConfirm: document.getElementById('btnConfirm'),
            btnSwitch: document.getElementById('btnSwitch'),
            cameraInfo: document.getElementById('cameraInfo'),
            infoCamera: document.getElementById('infoCamera'),
            infoResolution: document.getElementById('infoResolution')
        };
    }

    attachEvents() {
        // Capturar foto
        this.elements.btnCapture.addEventListener('click', () => this.capturePhoto());
        
        // Retomar foto
        this.elements.btnRetake.addEventListener('click', () => this.retakePhoto());
        
        // Confirmar y procesar
        this.elements.btnConfirm.addEventListener('click', () => this.confirmPhoto());
        
        // Cambiar cámara
        this.elements.btnSwitch.addEventListener('click', () => this.switchCamera());
    }

    async startCamera() {
        try {
            // Detener stream anterior si existe
            if (this.stream) {
                this.stopCamera();
            }

            // Solicitar acceso a cámara
            const constraints = {
                video: {
                    width: { ideal: this.config.width },
                    height: { ideal: this.config.height },
                    facingMode: this.currentFacingMode
                },
                audio: false
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.elements.video.srcObject = this.stream;

            // Esperar a que el video esté listo
            await new Promise((resolve) => {
                this.elements.video.onloadedmetadata = resolve;
            });

            // Actualizar info técnica
            const track = this.stream.getVideoTracks()[0];
            const settings = track.getSettings();
            this.elements.infoCamera.textContent = this.currentFacingMode === 'environment' ? 'Posterior' : 'Frontal';
            this.elements.infoResolution.textContent = `${settings.width}x${settings.height}`;

            // Callback
            if (this.config.onCameraReady) {
                this.config.onCameraReady(settings);
            }

        } catch (error) {
            console.error('Error al acceder a la cámara:', error);
            
            let errorMessage = 'No se pudo acceder a la cámara. ';
            if (error.name === 'NotAllowedError') {
                errorMessage += 'Permiso denegado. Por favor, permita el acceso a la cámara.';
            } else if (error.name === 'NotFoundError') {
                errorMessage += 'No se encontró ninguna cámara en el dispositivo.';
            } else {
                errorMessage += error.message;
            }

            if (this.config.onError) {
                this.config.onError(error, errorMessage);
            } else {
                alert(errorMessage);
            }
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            this.elements.video.srcObject = null;
        }
    }

    async switchCamera() {
        // Alternar entre cámaras
        this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
        await this.startCamera();
    }

    capturePhoto() {
        const video = this.elements.video;
        const canvas = this.elements.canvas;
        const context = canvas.getContext('2d');

        // Ajustar canvas al tamaño del video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        // Dibujar frame actual del video
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Convertir a blob
        canvas.toBlob(
            (blob) => {
                this.photoBlob = blob;
                this.photoDataUrl = canvas.toDataURL(this.config.imageFormat, this.config.imageQuality);

                // Mostrar preview
                this.showPreview();

                // Callback
                if (this.config.onPhotoTaken) {
                    this.config.onPhotoTaken({
                        blob: this.photoBlob,
                        dataUrl: this.photoDataUrl,
                        width: canvas.width,
                        height: canvas.height,
                        size: blob.size
                    });
                }
            },
            this.config.imageFormat,
            this.config.imageQuality
        );
    }

    showPreview() {
        // Mostrar imagen capturada
        this.elements.photoImage.src = this.photoDataUrl;
        
        // Información de la foto
        const sizeMB = (this.photoBlob.size / 1024 / 1024).toFixed(2);
        this.elements.photoSize.textContent = `${sizeMB} MB`;
        this.elements.photoResolution.textContent = `${this.elements.canvas.width}x${this.elements.canvas.height}`;

        // Cambiar UI
        this.elements.cameraView.style.display = 'none';
        this.elements.photoPreview.style.display = 'block';
        this.elements.controlsVideo.style.display = 'none';
        this.elements.controlsPhoto.style.display = 'flex';

        // Detener cámara para ahorrar recursos
        this.stopCamera();
    }

    retakePhoto() {
        // Volver a modo cámara
        this.elements.cameraView.style.display = 'block';
        this.elements.photoPreview.style.display = 'none';
        this.elements.controlsVideo.style.display = 'flex';
        this.elements.controlsPhoto.style.display = 'none';

        // Limpiar foto
        this.photoBlob = null;
        this.photoDataUrl = null;

        // Reiniciar cámara
        this.startCamera();
    }

    async confirmPhoto() {
        if (!this.photoBlob) {
            alert('No hay foto para confirmar');
            return;
        }

        // Mostrar estado de carga
        this.showLoading(true);

        try {
            // Generar nombre único para la foto
            const fileName = this.generateFileName();

            // Crear FormData para enviar
            const formData = new FormData();
            formData.append('file', this.photoBlob, fileName);
            formData.append('width', this.elements.canvas.width);
            formData.append('height', this.elements.canvas.height);
            formData.append('size', this.photoBlob.size);
            formData.append('timestamp', new Date().toISOString());

            // Retornar FormData para que el componente padre lo procese
            return {
                formData,
                fileName,
                blob: this.photoBlob,
                dataUrl: this.photoDataUrl
            };

        } catch (error) {
            console.error('Error al confirmar foto:', error);
            if (this.config.onError) {
                this.config.onError(error, 'Error al procesar la foto');
            }
            throw error;
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        this.elements.loadingState.style.display = show ? 'flex' : 'none';
        this.elements.controlsPhoto.style.display = show ? 'none' : 'flex';
    }

    generateFileName() {
        // Generar nombre único: YYYYMMDD_HHMMSS_UUID
        const now = new Date();
        const dateStr = now.getFullYear() +
            String(now.getMonth() + 1).padStart(2, '0') +
            String(now.getDate()).padStart(2, '0');
        const timeStr = String(now.getHours()).padStart(2, '0') +
            String(now.getMinutes()).padStart(2, '0') +
            String(now.getSeconds()).padStart(2, '0');
        const uuid = this.generateUUID();
        
        return `hoja_respuesta_${dateStr}_${timeStr}_${uuid}.jpg`;
    }

    generateUUID() {
        // Generar UUID simple
        return 'xxxx-xxxx-xxxx'.replace(/x/g, () => {
            return Math.floor(Math.random() * 16).toString(16);
        });
    }

    // Método público para resetear completamente
    reset() {
        this.stopCamera();
        this.photoBlob = null;
        this.photoDataUrl = null;
        this.elements.cameraView.style.display = 'block';
        this.elements.photoPreview.style.display = 'none';
        this.elements.controlsVideo.style.display = 'flex';
        this.elements.controlsPhoto.style.display = 'none';
    }

    // Método público para obtener la foto actual
    getPhoto() {
        return {
            blob: this.photoBlob,
            dataUrl: this.photoDataUrl
        };
    }

    // Método para mostrar/ocultar info técnica
    toggleDebugInfo(show) {
        this.elements.cameraInfo.style.display = show ? 'block' : 'none';
    }
}

// Exportar para uso global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CameraCapture;
}