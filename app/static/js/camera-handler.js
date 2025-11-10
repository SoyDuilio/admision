/* ==============================================
   CAMERA HANDLER - Manejo de cámara del dispositivo
   Soporta alternancia entre cámara frontal y trasera
   ============================================== */

class CameraHandler {
    constructor(videoElementId, canvasElementId) {
        this.video = document.getElementById(videoElementId);
        this.canvas = document.getElementById(canvasElementId);
        this.stream = null;
        this.currentFacingMode = 'environment'; // 'environment' = trasera, 'user' = frontal
        this.devices = [];
        this.currentDeviceIndex = 0;
    }

    async initialize() {
        try {
            // Obtener lista de dispositivos de video
            await this.getVideoDevices();
            
            // Iniciar con cámara trasera si está disponible
            await this.startCamera();
            
            console.log('✅ Cámara inicializada correctamente');
            return true;
        } catch (error) {
            console.error('❌ Error inicializando cámara:', error);
            this.showError('No se pudo acceder a la cámara. Verifica los permisos.');
            return false;
        }
    }

    async getVideoDevices() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.devices = devices.filter(device => device.kind === 'videoinput');
            console.log(`📹 Cámaras encontradas: ${this.devices.length}`);
            return this.devices;
        } catch (error) {
            console.error('Error obteniendo dispositivos:', error);
            return [];
        }
    }

    async startCamera() {
        try {
            // Detener stream anterior si existe
            if (this.stream) {
                this.stopCamera();
            }

            // Configuración de constraints
            const constraints = {
                video: {
                    facingMode: this.currentFacingMode,
                    width: { ideal: 1920 },
                    height: { ideal: 1080 }
                },
                audio: false
            };

            // Solicitar acceso a la cámara
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Asignar stream al video
            this.video.srcObject = this.stream;
            
            // Esperar a que el video esté listo
            await new Promise((resolve) => {
                this.video.onloadedmetadata = () => {
                    this.video.play();
                    resolve();
                };
            });

            console.log('✅ Cámara iniciada:', this.currentFacingMode);
            return true;

        } catch (error) {
            console.error('❌ Error iniciando cámara:', error);
            
            // Intentar con configuración alternativa si falla
            if (this.currentFacingMode === 'environment') {
                console.log('⚠️ Intentando con cámara frontal...');
                this.currentFacingMode = 'user';
                return await this.startCamera();
            }
            
            throw error;
        }
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            console.log('🛑 Cámara detenida');
        }
    }

    async switchCamera() {
        try {
            // Alternar entre frontal y trasera
            this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
            
            console.log('🔄 Cambiando a:', this.currentFacingMode);
            
            await this.startCamera();
            
            return true;
        } catch (error) {
            console.error('❌ Error alternando cámara:', error);
            
            // Revertir si falla
            this.currentFacingMode = this.currentFacingMode === 'environment' ? 'user' : 'environment';
            
            this.showError('No se pudo cambiar de cámara');
            return false;
        }
    }

    captureImage() {
        try {
            // Configurar canvas con las dimensiones del video
            this.canvas.width = this.video.videoWidth;
            this.canvas.height = this.video.videoHeight;

            // Dibujar frame actual del video en el canvas
            const ctx = this.canvas.getContext('2d');
            ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

            // Obtener imagen como data URL
            const imageDataUrl = this.canvas.toDataURL('image/jpeg', 0.9);
            
            console.log('📸 Imagen capturada');
            
            return imageDataUrl;

        } catch (error) {
            console.error('❌ Error capturando imagen:', error);
            this.showError('Error al capturar la imagen');
            return null;
        }
    }

    async captureImageBlob() {
        try {
            this.canvas.width = this.video.videoWidth;
            this.canvas.height = this.video.videoHeight;

            const ctx = this.canvas.getContext('2d');
            ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

            // Convertir canvas a Blob
            return new Promise((resolve) => {
                this.canvas.toBlob((blob) => {
                    resolve(blob);
                }, 'image/jpeg', 0.9);
            });

        } catch (error) {
            console.error('❌ Error capturando imagen como Blob:', error);
            return null;
        }
    }

    showError(message) {
        // Crear alerta temporal
        const alert = document.createElement('div');
        alert.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #dc2626;
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        alert.textContent = message;
        
        document.body.appendChild(alert);
        
        setTimeout(() => {
            alert.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }, 3000);
    }

    isActive() {
        return this.stream !== null && this.stream.active;
    }
}

// Agregar animaciones CSS
const style = document.createElement('style');
style.textContent = `
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
`;
document.head.appendChild(style);

// Exportar para uso global
window.CameraHandler = CameraHandler;