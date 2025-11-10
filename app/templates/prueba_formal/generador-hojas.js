// ===================================
// POSTULANDO - Generador de Hojas
// JavaScript Mejorado v2.0
// ===================================

class GeneradorHojas {
    constructor() {
        this.inicializar();
    }

    inicializar() {
        // Escuchar click en botón de generar hojas
        const btnGenerar = document.getElementById('btn-generar-hojas');
        if (btnGenerar) {
            btnGenerar.addEventListener('click', () => this.generarHojas());
        }

        // Escuchar cambios en selectores
        const selectores = document.querySelectorAll('.form-select');
        selectores.forEach(select => {
            select.addEventListener('change', () => this.validarFormulario());
        });
    }

    validarFormulario() {
        const numPostulantes = document.getElementById('num-postulantes')?.value || '';
        const btnGenerar = document.getElementById('btn-generar-hojas');
        
        if (btnGenerar) {
            btnGenerar.disabled = !numPostulantes || parseInt(numPostulantes) < 1;
        }
        
        return numPostulantes && parseInt(numPostulantes) > 0;
    }

    generarCodigoSeguridad() {
        // Genera un código de seguridad alfanumérico de 12 caracteres
        const caracteres = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        let codigo = '';
        
        for (let i = 0; i < 12; i++) {
            if (i > 0 && i % 4 === 0) {
                codigo += '-';
            }
            codigo += caracteres.charAt(Math.floor(Math.random() * caracteres.length));
        }
        
        return codigo;
    }

    generarDNI() {
        // Genera un DNI peruano válido (8 dígitos)
        return String(Math.floor(Math.random() * 90000000) + 10000000);
    }

    generarNombreAleatorio() {
        const nombres = [
            'Juan Carlos', 'María Elena', 'José Luis', 'Ana Patricia',
            'Carlos Alberto', 'Rosa María', 'Luis Miguel', 'Carmen Rosa',
            'Pedro Pablo', 'Sandra Luz', 'Miguel Ángel', 'Patricia Isabel',
            'Jorge Luis', 'Claudia Beatriz', 'Roberto Carlos', 'Vanessa Nicole'
        ];
        
        const apellidos = [
            'García López', 'Rodríguez Pérez', 'Fernández Torres', 'López Martínez',
            'González Ramírez', 'Martínez Flores', 'Sánchez Vargas', 'Pérez Castro',
            'Ramírez Mendoza', 'Torres Silva', 'Flores Quispe', 'Vargas Rojas',
            'Castro Díaz', 'Mendoza Vega', 'Silva Morales', 'Quispe Huamán'
        ];
        
        const nombre = nombres[Math.floor(Math.random() * nombres.length)];
        const apellido = apellidos[Math.floor(Math.random() * apellidos.length)];
        
        return `${apellido}, ${nombre}`;
    }

    async generarHojas() {
        if (!this.validarFormulario()) {
            this.mostrarAlerta('Por favor, completa todos los campos requeridos', 'warning');
            return;
        }

        const numPostulantes = parseInt(document.getElementById('num-postulantes')?.value || 0);
        const apiVision = document.getElementById('api-vision')?.value || 'google';
        
        // Mostrar loading
        this.mostrarLoading();

        try {
            // Simular generación de hojas
            await this.simularGeneracion(numPostulantes, apiVision);
            
            // Generar PDF con las hojas
            this.generarPDF(numPostulantes, apiVision);
            
            this.mostrarAlerta(`Se generaron ${numPostulantes} hojas de respuesta exitosamente`, 'success');
        } catch (error) {
            console.error('Error generando hojas:', error);
            this.mostrarAlerta('Error al generar las hojas. Por favor, intenta nuevamente.', 'danger');
        } finally {
            this.ocultarLoading();
        }
    }

    async simularGeneracion(numPostulantes, apiVision) {
        // Simular tiempo de procesamiento
        return new Promise(resolve => setTimeout(resolve, 1500));
    }

    generarPDF(numPostulantes, apiVision) {
        // Crear un nuevo documento
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        
        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const margen = 15;
        
        for (let i = 0; i < numPostulantes; i++) {
            if (i > 0) {
                doc.addPage();
            }
            
            const codigoSeguridad = this.generarCodigoSeguridad();
            const dni = this.generarDNI();
            const nombre = this.generarNombreAleatorio();
            const aula = `A-${String(Math.floor(i / 30) + 1).padStart(2, '0')}`;
            const numeroPostulante = String(i + 1).padStart(3, '0');
            
            // Header
            doc.setFillColor(102, 102, 241);
            doc.rect(0, 0, pageWidth, 30, 'F');
            
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(20);
            doc.setFont(undefined, 'bold');
            doc.text('🎓 POSTULANDO', margen, 15);
            
            doc.setFontSize(10);
            doc.setFont(undefined, 'normal');
            doc.text('Sistema de Exámenes de Admisión', margen, 22);
            
            // Información del postulante
            doc.setTextColor(0, 0, 0);
            doc.setFontSize(12);
            doc.setFont(undefined, 'bold');
            doc.text('HOJA DE RESPUESTAS - PROCESO DE ADMISIÓN 2025', margen, 45);
            
            // Datos personales
            let y = 60;
            doc.setFontSize(10);
            doc.setFont(undefined, 'bold');
            doc.text('DATOS DEL POSTULANTE:', margen, y);
            
            y += 10;
            doc.setFont(undefined, 'normal');
            doc.text(`Código de Postulante: ${numeroPostulante}`, margen + 5, y);
            
            y += 8;
            doc.text(`DNI: ${dni}`, margen + 5, y);
            
            y += 8;
            doc.text(`Nombre: ${nombre}`, margen + 5, y);
            
            y += 8;
            doc.text(`Aula: ${aula}`, margen + 5, y);
            
            y += 8;
            doc.text(`Procesamiento: API ${apiVision.toUpperCase()}`, margen + 5, y);
            
            // Código de seguridad
            y += 15;
            doc.setFillColor(30, 41, 59);
            doc.roundedRect(margen, y, pageWidth - (margen * 2), 25, 3, 3, 'F');
            
            doc.setTextColor(255, 255, 255);
            doc.setFontSize(9);
            doc.text('CÓDIGO DE SEGURIDAD', pageWidth / 2, y + 7, { align: 'center' });
            
            doc.setFontSize(16);
            doc.setFont('courier', 'bold');
            doc.text(codigoSeguridad, pageWidth / 2, y + 18, { align: 'center' });
            
            // Instrucciones
            y += 35;
            doc.setTextColor(0, 0, 0);
            doc.setFontSize(10);
            doc.setFont(undefined, 'bold');
            doc.text('INSTRUCCIONES:', margen, y);
            
            y += 8;
            doc.setFont(undefined, 'normal');
            doc.setFontSize(9);
            const instrucciones = [
                '1. Use lápiz HB para marcar sus respuestas',
                '2. Rellene completamente el círculo de la alternativa elegida',
                '3. Para cambiar una respuesta, borre completamente y marque la nueva',
                '4. No doble ni arrugue esta hoja',
                '5. El código de seguridad es único e intransferible'
            ];
            
            instrucciones.forEach((inst, idx) => {
                doc.text(inst, margen + 5, y + (idx * 6));
            });
            
            // Cuadrícula de respuestas
            y += 40;
            doc.setFont(undefined, 'bold');
            doc.setFontSize(10);
            doc.text('HOJA DE RESPUESTAS (100 preguntas):', margen, y);
            
            y += 8;
            const inicioY = y;
            const radioCirculo = 3;
            const espacioH = 35;
            const espacioV = 8;
            
            // Generar 100 preguntas en 4 columnas
            for (let pregunta = 1; pregunta <= 100; pregunta++) {
                const columna = Math.floor((pregunta - 1) / 25);
                const fila = (pregunta - 1) % 25;
                
                const x = margen + (columna * espacioH);
                const yPos = inicioY + (fila * espacioV);
                
                // Número de pregunta
                doc.setFontSize(8);
                doc.text(String(pregunta).padStart(2, '0'), x, yPos);
                
                // Alternativas A, B, C, D, E
                const alternativas = ['A', 'B', 'C', 'D', 'E'];
                alternativas.forEach((alt, idx) => {
                    const xCirculo = x + 10 + (idx * 4);
                    doc.circle(xCirculo, yPos - 1.5, radioCirculo, 'S');
                    doc.setFontSize(6);
                    doc.text(alt, xCirculo - 0.8, yPos - 1);
                });
            }
            
            // Footer
            doc.setFontSize(8);
            doc.setTextColor(100, 100, 100);
            doc.text(`Generado: ${new Date().toLocaleString('es-PE')}`, margen, pageHeight - 10);
            doc.text(`Página ${i + 1} de ${numPostulantes}`, pageWidth - margen - 30, pageHeight - 10);
        }
        
        // Descargar el PDF
        const fecha = new Date().toISOString().split('T')[0];
        doc.save(`POSTULANDO_Hojas_${fecha}_${numPostulantes}postulantes.pdf`);
    }

    mostrarLoading() {
        const btn = document.getElementById('btn-generar-hojas');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="loading-spinner"></span> Generando...';
        }
    }

    ocultarLoading() {
        const btn = document.getElementById('btn-generar-hojas');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '📄 Generar Hojas de Respuestas';
        }
    }

    mostrarAlerta(mensaje, tipo = 'info') {
        // Buscar contenedor de alertas o crear uno
        let contenedor = document.getElementById('alertas-container');
        if (!contenedor) {
            contenedor = document.createElement('div');
            contenedor.id = 'alertas-container';
            contenedor.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
            document.body.appendChild(contenedor);
        }

        const alerta = document.createElement('div');
        alerta.className = `alert alert-${tipo}`;
        alerta.style.cssText = 'margin-bottom: 10px; animation: slideIn 0.3s ease;';
        alerta.innerHTML = `
            <span>${this.getIconoAlerta(tipo)}</span>
            <span>${mensaje}</span>
        `;

        contenedor.appendChild(alerta);

        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            alerta.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => alerta.remove(), 300);
        }, 5000);
    }

    getIconoAlerta(tipo) {
        const iconos = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'danger': '❌'
        };
        return iconos[tipo] || iconos.info;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    new GeneradorHojas();
});

// Animaciones CSS adicionales
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