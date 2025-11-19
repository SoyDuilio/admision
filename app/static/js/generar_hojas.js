/**
 * Sistema de Generación de Hojas - JavaScript
 * app/static/js/generar_hojas.js
 * 
 * Incluye:
 * - Generación por aula con verificación
 * - Generación individual
 * - Sistema de confirmación para regeneración
 */

// ============================================================================
// VARIABLES GLOBALES
// ============================================================================

let aulasDisponibles = [];
let aulaParaRegenerar = null;
let postulanteSeleccionado = null;


// ============================================================================
// MODAL DE GENERACIÓN POR AULA
// ============================================================================

async function abrirModalHojasAula() {
    document.getElementById('modalGenerarHojasAula').style.display = 'flex';
    await verificarAsignaciones();
}

function cerrarModalHojasAula() {
    document.getElementById('modalGenerarHojasAula').style.display = 'none';
}

async function verificarAsignaciones() {
    try {
        const response = await fetch('/api/verificar-asignaciones-completas?proceso=2025-2');
        const data = await response.json();
        
        // Actualizar contadores
        document.getElementById('totalAulas').textContent = data.total_aulas || 10;
        document.getElementById('totalAsignados').textContent = data.total_asignados || 0;
        document.getElementById('totalSinAsignar').textContent = data.sin_asignar || 0;
        
        if (!data.puede_generar_hojas) {
            document.getElementById('alertaIncompleto').style.display = 'block';
            document.getElementById('opcionesGeneracion').style.display = 'none';
        } else {
            document.getElementById('alertaIncompleto').style.display = 'none';
            document.getElementById('opcionesGeneracion').style.display = 'block';
        }
        
    } catch (error) {
        console.error('Error:', error);
    }
}

async function seleccionarOpcionTodas() {
    if (!confirm('¿Generar hojas para TODAS las aulas?')) {
        return;
    }
    
    try {
        mostrarProgreso('Generando hojas para todas las aulas...');
        
        const response = await fetch('/api/generar-todas-las-aulas', { method: 'POST' });
        const data = await response.json();
        
        ocultarProgreso();
        
        if (data.success) {
            alert(`✅ Generación completada\n\nAulas procesadas: ${data.total_aulas_procesadas}`);
            cerrarModalHojasAula();
        } else {
            alert('❌ Error: ' + data.mensaje);
        }
        
    } catch (error) {
        ocultarProgreso();
        console.error('Error:', error);
        alert('Error al generar hojas');
    }
}

async function seleccionarOpcionEspecifica() {
    try {
        mostrarProgreso('Cargando aulas...');
        
        const response = await fetch('/api/aulas-con-asignaciones?proceso=2025-2');
        const data = await response.json();
        
        ocultarProgreso();
        
        if (data.success) {
            aulasDisponibles = data.aulas;
            mostrarListaAulas(data.aulas);
        } else {
            alert('Error al cargar aulas');
        }
        
    } catch (error) {
        ocultarProgreso();
        console.error('Error:', error);
        alert('Error al cargar aulas');
    }
}

function mostrarListaAulas(aulas) {
    const container = document.getElementById('listaAulasContainer');
    
    if (aulas.length === 0) {
        container.innerHTML = '<p>No hay aulas con postulantes asignados</p>';
        return;
    }
    
    let html = '<div class="aulas-grid">';
    
    aulas.forEach(aula => {
        html += `
            <div class="aula-card" onclick="generarHojasAula(${aula.aula_id})">
                <div class="aula-header">
                    <span class="aula-codigo">${aula.codigo_aula}</span>
                    <span class="aula-badge">${aula.postulantes_asignados} estudiantes</span>
                </div>
                <div class="aula-nombre">${aula.nombre}</div>
                <div class="aula-ubicacion">📍 ${aula.edificio} - Piso ${aula.piso}</div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
    
    document.getElementById('opcionesGeneracion').style.display = 'none';
    document.getElementById('listaAulas').style.display = 'block';
}

async function generarHojasAula(aulaId) {
    try {
        // VERIFICAR si ya tiene hojas generadas
        const verificacionResponse = await fetch(`/api/verificar-hojas-aula/${aulaId}`);
        const verificacion = await verificacionResponse.json();
        
        if (verificacion.hojas_generadas) {
            // Ya tiene hojas - pedir confirmación
            const aula = aulasDisponibles.find(a => a.aula_id === aulaId);
            abrirModalConfirmarRegeneracion(aula, verificacion);
            return;
        }
        
        // NO tiene hojas - generar directamente
        await ejecutarGeneracionAula(aulaId);
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error al generar hojas');
    }
}

async function ejecutarGeneracionAula(aulaId) {
    try {
        mostrarProgreso('Generando hojas para aula...');
        
        const response = await fetch(`/api/generar-hojas-aula/${aulaId}`);
        const data = await response.json();
        
        ocultarProgreso();
        
        if (data.success) {
            alert(`✅ Hojas generadas exitosamente\n\nAula: ${data.aula.codigo}\nTotal: ${data.total_postulantes} hojas`);
            cerrarModalHojasAula();
        } else {
            alert('❌ Error: ' + data.mensaje);
        }
        
    } catch (error) {
        ocultarProgreso();
        console.error('Error:', error);
        alert('Error al generar hojas');
    }
}


// ============================================================================
// MODAL DE CONFIRMACIÓN DE REGENERACIÓN
// ============================================================================

function abrirModalConfirmarRegeneracion(aula, datosGeneracion) {
    aulaParaRegenerar = aula;
    
    // Llenar datos
    document.getElementById('confirmarAulaCodigo').textContent = aula.codigo_aula;
    document.getElementById('confirmarAulaNombre').textContent = aula.nombre;
    document.getElementById('confirmarAulaPostulantes').textContent = aula.postulantes_asignados;
    
    document.getElementById('fechaGeneracionAnterior').textContent = datosGeneracion.mensaje;
    document.getElementById('totalHojasAnteriores').textContent = datosGeneracion.total_hojas;
    
    // Mostrar modal
    document.getElementById('modalConfirmarRegeneracion').style.display = 'flex';
    
    // Reset form
    document.getElementById('motivoRegeneracion').value = '';
    document.getElementById('autorizadoPor').value = '';
    document.getElementById('cargoAutoriza').value = '';
    document.getElementById('fraseConfirmacion').value = '';
    document.getElementById('errorFrase').style.display = 'none';
}

function cerrarModalRegeneracion() {
    document.getElementById('modalConfirmarRegeneracion').style.display = 'none';
    aulaParaRegenerar = null;
}

async function confirmarRegeneracion() {
    // Validar campos
    const motivo = document.getElementById('motivoRegeneracion').value;
    const autorizadoPor = document.getElementById('autorizadoPor').value;
    const cargo = document.getElementById('cargoAutoriza').value;
    const frase = document.getElementById('fraseConfirmacion').value.trim().toLowerCase();
    
    if (!motivo || !autorizadoPor || !cargo) {
        alert('Complete todos los campos obligatorios');
        return;
    }
    
    if (motivo === 'otro' && !document.getElementById('otroMotivoRegeneracion').value) {
        alert('Especifique el motivo');
        return;
    }
    
    // Validar frase
    if (frase !== 'anular hojas anteriores') {
        document.getElementById('errorFrase').style.display = 'block';
        return;
    }
    
    if (!confirm('¿Está seguro? Esta acción NO se puede deshacer.')) {
        return;
    }
    
    // Regenerar
    try {
        const motivoFinal = motivo === 'otro' 
            ? document.getElementById('otroMotivoRegeneracion').value 
            : motivo;
        
        const response = await fetch(`/api/regenerar-hojas-aula/${aulaParaRegenerar.aula_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                motivo: motivoFinal,
                autorizado_por: autorizadoPor,
                cargo: cargo
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Hojas regeneradas\n\nTotal: ${data.total_hojas}`);
            cerrarModalRegeneracion();
            cerrarModalHojasAula();
        } else {
            alert('❌ Error: ' + data.message);
        }
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error al regenerar');
    }
}


// ============================================================================
// MODAL DE GENERACIÓN INDIVIDUAL
// ============================================================================

function abrirModalHojaIndividual() {
    cerrarModalHojasAula();
    document.getElementById('modalGenerarHojaIndividual').style.display = 'flex';
    resetearModalIndividual();
}

function cerrarModalHojaIndividual() {
    document.getElementById('modalGenerarHojaIndividual').style.display = 'none';
    resetearModalIndividual();
}

function resetearModalIndividual() {
    document.getElementById('paso1-buscar').style.display = 'block';
    document.getElementById('paso2-datos').style.display = 'none';
    document.getElementById('paso3-confirmacion').style.display = 'none';
    
    document.getElementById('inputDNI').value = '';
    document.getElementById('inputCodigo').value = '';
    
    postulanteSeleccionado = null;
}

function cambiarTipoBusqueda() {
    const tipo = document.querySelector('input[name="tipoBusqueda"]:checked').value;
    document.getElementById('groupDNI').style.display = tipo === 'dni' ? 'block' : 'none';
    document.getElementById('groupCodigo').style.display = tipo === 'codigo' ? 'block' : 'none';
}

async function buscarPostulante() {
    const tipo = document.querySelector('input[name="tipoBusqueda"]:checked').value;
    const valor = tipo === 'dni' 
        ? document.getElementById('inputDNI').value 
        : document.getElementById('inputCodigo').value;
    
    if (!valor) {
        alert('Ingrese un valor para buscar');
        return;
    }
    
    try {
        const response = await fetch(`/api/buscar-postulante?tipo=${tipo}&valor=${valor}`);
        const data = await response.json();
        
        if (data.success) {
            mostrarDatosPostulante(data.postulante);
        } else {
            alert('No se encontró: ' + data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al buscar');
    }
}

function mostrarDatosPostulante(postulante) {
    postulanteSeleccionado = postulante;
    
    document.getElementById('datoDNI').textContent = postulante.dni;
    document.getElementById('datoNombre').textContent = postulante.nombre_completo;
    document.getElementById('datoPrograma').textContent = postulante.programa;
    document.getElementById('datoAula').textContent = postulante.aula || 'Sin asignar';
    
    if (postulante.hoja_anterior) {
        document.getElementById('alertaHojaExistente').style.display = 'block';
        document.getElementById('codigoAnterior').textContent = postulante.hoja_anterior.codigo;
        document.getElementById('fechaAnterior').textContent = postulante.hoja_anterior.fecha;
        document.getElementById('estadoAnterior').textContent = postulante.hoja_anterior.estado;
    } else {
        document.getElementById('alertaHojaExistente').style.display = 'none';
    }
    
    document.getElementById('paso1-buscar').style.display = 'none';
    document.getElementById('paso2-datos').style.display = 'block';
}

function toggleOtroMotivo() {
    const motivo = document.getElementById('selectMotivo').value;
    document.getElementById('groupOtroMotivo').style.display = motivo === 'otro' ? 'block' : 'none';
}

function volverAPaso1() {
    document.getElementById('paso2-datos').style.display = 'none';
    document.getElementById('paso1-buscar').style.display = 'block';
}

async function confirmarGeneracion() {
    const motivo = document.getElementById('selectMotivo').value;
    const solicitadoPor = document.getElementById('solicitadoPor').value;
    
    if (!motivo || !solicitadoPor) {
        alert('Complete todos los campos obligatorios (*)');
        return;
    }
    
    if (motivo === 'otro' && !document.getElementById('otroMotivo').value) {
        alert('Especifique el motivo');
        return;
    }
    
    const data = {
        postulante_id: postulanteSeleccionado.id,
        motivo: motivo === 'otro' ? document.getElementById('otroMotivo').value : motivo,
        solicitado_por: solicitadoPor,
        entrego_anterior: document.getElementById('checkEntregoAnterior').checked,
        observaciones: document.getElementById('observaciones').value
    };
    
    try {
        const response = await fetch('/api/generar-hoja-individual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('nuevoCodigoHoja').textContent = result.codigo_hoja;
            document.getElementById('paso2-datos').style.display = 'none';
            document.getElementById('paso3-confirmacion').style.display = 'block';
        } else {
            alert('Error: ' + result.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error al generar hoja');
    }
}

function descargarHoja() {
    const codigo = document.getElementById('nuevoCodigoHoja').textContent;
    window.open(`/api/descargar-hoja/${codigo}`, '_blank');
}


// ============================================================================
// UTILIDADES
// ============================================================================

function mostrarProgreso(mensaje) {
    // Implementar spinner o loader
    console.log(mensaje);
}

function ocultarProgreso() {
    // Ocultar spinner
}

// Event listeners para select de motivo en regeneración
document.addEventListener('DOMContentLoaded', function() {
    const selectMotivo = document.getElementById('motivoRegeneracion');
    if (selectMotivo) {
        selectMotivo.addEventListener('change', function() {
            document.getElementById('groupOtroMotivoRegeneracion').style.display = 
                this.value === 'otro' ? 'block' : 'none';
        });
    }
});