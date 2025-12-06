/* ============================================================
   POSTULANDO - Dashboard Coordinador JavaScript
   static/js/admin/dashboard_coordinador.js
   ============================================================ */

let currentFilters = {};
let paginationState = { page: 1, perPage: 20, total: 0 };

// ============================================================
// GESTIÓN DE POSTULANTES
// ============================================================

async function cargarPostulantes(page = 1) {
    const container = document.getElementById('listaPostulantes');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center p-4"><div class="spinner"></div> Cargando...</div>';
    
    try {
        const params = new URLSearchParams({ page, per_page: 20, ...currentFilters });
        const data = await apiGet(`/admin/api/postulantes?${params}`);
        
        paginationState.page = page;
        paginationState.total = data.total;
        
        renderPostulantes(data.postulantes);
    } catch (error) {
        container.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
    }
}

function renderPostulantes(postulantes) {
    const container = document.getElementById('listaPostulantes');
    
    if (!postulantes || postulantes.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="icon">👥</div><h3>No hay postulantes</h3></div>`;
        return;
    }
    
    let html = `<div class="table-container"><table class="table"><thead><tr>
        <th>DNI</th><th>Apellidos y Nombres</th><th>Programa</th><th>Aula</th><th>Acciones</th>
    </tr></thead><tbody>`;
    
    postulantes.forEach(p => {
        html += `<tr>
            <td><strong>${p.dni}</strong></td>
            <td>${p.apellido_paterno} ${p.apellido_materno}, ${p.nombres}</td>
            <td>${p.programa_educativo || '-'}</td>
            <td>${p.aula_codigo ? `<span class="badge badge-success">${p.aula_codigo}</span>` : '<span class="badge badge-warning">Sin asignar</span>'}</td>
            <td>
                <button class="btn btn-outline btn-sm" onclick="editarPostulante(${p.id})">✏️</button>
                <button class="btn btn-outline btn-sm" onclick="eliminarPostulante(${p.id})">🗑️</button>
            </td>
        </tr>`;
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

async function registrarPostulante(event) {
    event.preventDefault();
    const form = event.target;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    
    try {
        const data = serializeForm(form);
        await apiPost('/admin/api/postulantes', data);
        showToast('Postulante registrado', 'success');
        form.reset();
        cargarPostulantes();
        actualizarContadores();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function editarPostulante(id) {
    try {
        const p = await apiGet(`/admin/api/postulantes/${id}`);
        document.getElementById('editId').value = p.id;
        document.getElementById('editDni').value = p.dni;
        document.getElementById('editNombres').value = p.nombres;
        document.getElementById('editApellidoPaterno').value = p.apellido_paterno;
        document.getElementById('editApellidoMaterno').value = p.apellido_materno;
        document.getElementById('editPrograma').value = p.programa_educativo || '';
        document.getElementById('modalEditarPostulante').classList.add('active');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function guardarEdicionPostulante(event) {
    event.preventDefault();
    const id = document.getElementById('editId').value;
    const btn = event.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    
    try {
        await apiPut(`/admin/api/postulantes/${id}`, serializeForm(event.target));
        showToast('Postulante actualizado', 'success');
        cerrarModal('modalEditarPostulante');
        cargarPostulantes(paginationState.page);
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

function eliminarPostulante(id) {
    confirmAction('¿Eliminar este postulante?', async () => {
        try {
            await apiDelete(`/admin/api/postulantes/${id}`);
            showToast('Postulante eliminado', 'success');
            cargarPostulantes();
            actualizarContadores();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });
}

async function cargarPostulantesMasivo(event) {
    event.preventDefault();
    const file = document.getElementById('archivoPostulantes').files[0];
    if (!file) { showToast('Seleccione un archivo', 'warning'); return; }
    
    const formData = new FormData();
    formData.append('archivo', file);
    const btn = event.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Procesando...';
    
    try {
        const response = await fetch('/admin/api/postulantes/carga-masiva', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.success) {
            showToast(`${data.registrados} postulantes registrados`, 'success');
            cargarPostulantes();
            actualizarContadores();
        } else {
            showToast(data.error, 'error');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '📤 Cargar Archivo';
    }
}

function filtrarPostulantes() {
    currentFilters = {
        dni: document.getElementById('filtroDni')?.value || '',
        apellidos: document.getElementById('filtroApellidos')?.value || '',
        programa: document.getElementById('filtroPrograma')?.value || ''
        // turno no existe en la BD, se omite
    };
    Object.keys(currentFilters).forEach(k => { if (!currentFilters[k]) delete currentFilters[k]; });
    cargarPostulantes(1);
}

// ============================================================
// GESTIÓN DE AULAS
// ============================================================

async function cargarAulas() {
    const container = document.getElementById('listaAulas');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center p-4"><div class="spinner"></div> Cargando...</div>';
    
    try {
        const data = await apiGet('/admin/api/aulas');
        renderAulas(data.aulas);
    } catch (error) {
        container.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
    }
}

function renderAulas(aulas) {
    const container = document.getElementById('listaAulas');
    
    if (!aulas || aulas.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="icon">🏫</div><h3>No hay aulas</h3></div>`;
        return;
    }
    
    let html = '<div class="aulas-grid">';
    aulas.forEach(a => {
        const pct = a.capacidad > 0 ? Math.round((a.asignados || 0) / a.capacidad * 100) : 0;
        html += `
            <div class="aula-card">
                <div class="aula-header">
                    <div class="aula-codigo">${a.codigo}</div>
                    <span class="badge ${a.activo ? 'badge-success' : 'badge-danger'}">${a.activo ? 'Activa' : 'Inactiva'}</span>
                </div>
                <div class="aula-info">
                    <div class="aula-info-item"><span>📍</span> ${a.nombre || 'Sin nombre'}</div>
                    <div class="aula-info-item"><span>🏢</span> ${a.programa || '-'} - Piso ${a.piso || '-'}</div>
                </div>
                <div class="aula-capacidad">
                    <div class="aula-capacidad-bar"><div class="aula-capacidad-fill" style="width:${pct}%"></div></div>
                    <span class="aula-capacidad-text">${a.asignados || 0}/${a.capacidad}</span>
                </div>
                <div class="aula-actions">
                    <button class="btn btn-outline btn-sm" onclick="editarAula(${a.id})">✏️ Editar</button>
                </div>
            </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

async function registrarAula(event) {
    event.preventDefault();
    const form = event.target;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    
    try {
        await apiPost('/admin/api/aulas', serializeForm(form));
        showToast('Aula registrada', 'success');
        form.reset();
        cargarAulas();
        actualizarContadores();
        actualizarPreviewCodigo();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

function actualizarPreviewCodigo() {
    const prefijo = document.getElementById('prefijoAula')?.value || 'AU';
    const preview = document.getElementById('previewCodigo');
    if (preview) {
        apiGet('/admin/api/aulas/siguiente-codigo?prefijo=' + prefijo)
            .then(data => preview.textContent = data.codigo)
            .catch(() => preview.textContent = prefijo + '-001');
    }
}

// ============================================================
// GESTIÓN DE PROFESORES
// ============================================================

async function cargarProfesores() {
    const container = document.getElementById('listaProfesores');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center p-4"><div class="spinner"></div> Cargando...</div>';
    
    try {
        const data = await apiGet('/admin/api/profesores');
        renderProfesores(data.profesores);
    } catch (error) {
        container.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
    }
}

function renderProfesores(profesores) {
    const container = document.getElementById('listaProfesores');
    
    if (!profesores || profesores.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="icon">👨‍🏫</div><h3>No hay profesores</h3></div>`;
        return;
    }
    
    let html = '<div class="profesores-grid">';
    profesores.forEach(p => {
        const ini = (p.nombres[0] + p.apellido_paterno[0]).toUpperCase();
        html += `
            <div class="profesor-card ${!p.habilitado ? 'inhabilitado' : ''}">
                <div class="profesor-header">
                    <div class="profesor-avatar ${p.condicion === 'EXTERNO' ? 'externo' : ''}">${ini}</div>
                    <div>
                        <div class="profesor-name">${p.apellido_paterno} ${p.apellido_materno || ''}, ${p.nombres}</div>
                        <div class="profesor-dni">DNI: ${p.dni}</div>
                        <span class="badge ${p.condicion === 'DOCENTE' ? 'badge-success' : p.condicion === 'ADMINISTRATIVO' ? 'badge-info' : 'badge-warning'}">${p.condicion}</span>
                    </div>
                </div>
                <div class="profesor-contacto">
                    ${p.email ? `<div><span>📧</span> ${p.email}</div>` : ''}
                    ${p.telefono ? `<div><span>📱</span> ${p.telefono}</div>` : ''}
                </div>
                ${!p.habilitado ? '<div class="profesor-warning">⚠️ No participará en próximos procesos</div>' : ''}
                <div class="aula-actions">
                    <button class="btn btn-outline btn-sm" onclick="editarProfesor(${p.id})">✏️</button>
                    <button class="btn btn-outline btn-sm" onclick="toggleHabilitacion(${p.id}, ${!p.habilitado})">${p.habilitado ? '🚫' : '✅'}</button>
                </div>
            </div>`;
    });
    html += '</div>';
    container.innerHTML = html;
}

async function registrarProfesor(event) {
    event.preventDefault();
    const form = event.target;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    
    try {
        await apiPost('/admin/api/profesores', serializeForm(form));
        showToast('Profesor registrado', 'success');
        form.reset();
        cargarProfesores();
        actualizarContadores();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function toggleHabilitacion(id, nuevoEstado) {
    confirmAction(`¿${nuevoEstado ? 'Habilitar' : 'Inhabilitar'} a este profesor?`, async () => {
        try {
            await apiPut(`/admin/api/profesores/${id}/habilitacion`, { habilitado: nuevoEstado });
            showToast('Estado actualizado', 'success');
            cargarProfesores();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });
}

// ============================================================
// LISTADOS
// ============================================================

// ============================================================================
// GESTIÓN DE LISTADOS
// ============================================================================

function seleccionarTipoListado(tipo) {
    console.log('🎯 INICIO - Tipo seleccionado:', tipo);
    
    // Desactivar todas
    const opciones = document.querySelectorAll('.listado-option');
    console.log('  📋 Total opciones:', opciones.length);
    
    opciones.forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // Activar seleccionada
    const selected = document.querySelector(`[data-listado="${tipo}"]`);
    if (selected) {
        selected.classList.add('selected');
        console.log('  ✅ Opción activada');
    } else {
        console.error('  ❌ No se encontró opción');
        return;
    }
    
    // Buscar contenedores
    const configAula = document.getElementById('config-por-aula');
    const configControl = document.getElementById('config-control-profesores');
    
    console.log('  📦 Contenedores:', {
        'config-por-aula': !!configAula,
        'config-control-profesores': !!configControl
    });
    
    // Ocultar todos
    if (configAula) configAula.classList.add('hidden');
    if (configControl) configControl.classList.add('hidden');
    
    // Mostrar el específico
    if (tipo === 'por-aula') {
        if (configAula) {
            configAula.classList.remove('hidden');
            console.log('  🔓 config-por-aula visible');
        }
    } else if (tipo === 'control-profesores') {
        if (configControl) {
            configControl.classList.remove('hidden');
            console.log('  🔓 config-control-profesores visible');
            
            // Cargar listas automáticamente
            console.log('  ⏳ Cargando listas de control...');
            if (typeof cargarListasControl === 'function') {
                cargarListasControl();
            } else {
                console.error('  ❌ cargarListasControl no existe');
            }
        }
    }
    
    // Ocultar/mostrar botón Generar
    const btnGenerar = document.getElementById('btnGenerarListado');
    if (btnGenerar) {
        btnGenerar.style.display = (tipo === 'control-profesores') ? 'none' : 'inline-block';
        console.log('  🔘 Botón Generar:', tipo === 'control-profesores' ? 'OCULTO' : 'VISIBLE');
    }
    
    console.log('✅ FIN - Función completada');
}

async function cargarListasControl() {
    console.log('📥 Cargando listas de control...');
    
    const container = document.getElementById('listasControlAulas');
    if (!container) {
        console.error('❌ No se encontró el contenedor listasControlAulas');
        return;
    }
    
    container.innerHTML = `
        <p style="text-align: center; color: #6c757d; padding: 40px;">
            <span style="font-size: 2rem;">⏳</span><br>
            Cargando aulas...
        </p>
    `;
    
    try {
        // Obtener el proceso actual (más robusto)
        let proceso = '2025-2'; // valor por defecto
        
        const procesoInput = document.querySelector('[name="proceso_admision"]');
        if (procesoInput && procesoInput.value) {
            proceso = procesoInput.value;
        } else {
            // Intentar obtenerlo del footer o header
            const procesoElement = document.querySelector('.header span strong, .footer span strong');
            if (procesoElement) {
                proceso = procesoElement.textContent.trim();
            }
        }
        
        const url = `/api/aulas-con-asignaciones?proceso=${proceso}&formato=simple`;
        console.log('🌐 Fetch:', url);
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const aulas = await response.json();
        console.log('✅ Aulas recibidas:', aulas);
        
        if (!aulas || aulas.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #6c757d;">
                    <span style="font-size: 3rem;">📭</span>
                    <h4 style="margin: 16px 0 8px 0;">No hay aulas con asignaciones</h4>
                    <p style="margin: 0; font-size: 0.9rem;">Primero debe generar las hojas de respuesta.</p>
                </div>
            `;
            return;
        }
        
        let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px;">';
        
        aulas.forEach(aula => {
            html += `
                <a href="/api/lista-control-aula/${aula.id}?proceso=${proceso}" 
                   target="_blank"
                   class="btn btn-outline"
                   style="display: flex; align-items: center; justify-content: space-between; text-decoration: none; padding: 16px; height: auto; min-height: 80px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 1.5rem;">🏫</span>
                        <div style="text-align: left;">
                            <strong style="display: block; font-size: 1rem; margin-bottom: 4px;">${aula.codigo}</strong>
                            <small style="color: #6c757d; font-size: 0.85rem;">${aula.nombre || 'Sin nombre'}</small>
                        </div>
                    </div>
                    <span style="background: #e9ecef; padding: 6px 12px; border-radius: 12px; font-size: 0.85em; font-weight: 600; white-space: nowrap;">
                        ${aula.total} alumnos
                    </span>
                </a>
            `;
        });
        
        html += '</div>';
        
        container.innerHTML = html;
        console.log('✅ Listas de control cargadas correctamente');
        
    } catch (error) {
        console.error('❌ Error cargando listas de control:', error);
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #dc3545;">
                <span style="font-size: 3rem;">❌</span>
                <h4 style="margin: 16px 0 8px 0;">Error al cargar las aulas</h4>
                <p style="margin: 0 0 16px 0; font-size: 0.9rem;">${error.message}</p>
                <button type="button" class="btn btn-outline" onclick="cargarListasControl()">🔄 Reintentar</button>
            </div>
        `;
    }
}

async function abrirTodasLasListasControl() {
    if (!confirm('Esta acción abrirá todas las listas de control en pestañas separadas.\n\nPodrá imprimir cada una con Ctrl+P.\n\n¿Continuar?')) {
        return;
    }
    
    try {
        // Obtener el proceso actual
        let proceso = '2025-2';
        const procesoInput = document.querySelector('[name="proceso_admision"]');
        if (procesoInput && procesoInput.value) {
            proceso = procesoInput.value;
        } else {
            const procesoElement = document.querySelector('.header span strong, .footer span strong');
            if (procesoElement) {
                proceso = procesoElement.textContent.trim();
            }
        }
        
        const response = await fetch(`/api/aulas-con-asignaciones?proceso=${proceso}&formato=simple`);
        const aulas = await response.json();
        
        if (!aulas || aulas.length === 0) {
            alert('No hay aulas con asignaciones');
            return;
        }
        
        console.log(`📥 Abriendo ${aulas.length} listas de control...`);
        
        aulas.forEach((aula, index) => {
            setTimeout(() => {
                const url = `/api/lista-control-aula/${aula.id}?proceso=${proceso}`;
                console.log(`🔗 Abriendo: ${url}`);
                window.open(url, '_blank');
            }, index * 500);
        });
        
    } catch (error) {
        alert('Error al abrir listas: ' + error.message);
    }
}

async function generarListado(tipo) {
    const btn = document.getElementById('btnGenerarListado');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generando...';
    
    try {
        const params = { tipo };
        
        // Validar que se haya seleccionado un aula si es por-aula
        if (tipo === 'por-aula') {
            const aulaId = document.getElementById('listadoAula')?.value;
            if (!aulaId) {
                showToast('Seleccione un aula', 'warning');
                btn.disabled = false;
                btn.innerHTML = '📄 Generar Listado';
                return;
            }
            params.aula_id = aulaId;
        }
        
        const data = await apiGet(`/admin/api/listados/preview?${new URLSearchParams(params)}`);
        
        const previewCard = document.getElementById('previewListadoCard');
        const previewContent = document.getElementById('previewListado');
        
        if (previewContent) {
            previewContent.innerHTML = data.html;
        }
        if (previewCard) {
            previewCard.classList.remove('hidden');
        }
        
        showToast('Listado generado', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '📄 Generar Listado';
    }
}

function imprimirListado() {
    const preview = document.getElementById('previewListado');
    if (!preview || !preview.innerHTML.trim()) {
        showToast('Primero genere un listado', 'warning');
        return;
    }
    
    const w = window.open('', '_blank');
    w.document.write(`<!DOCTYPE html>
<html>
<head>
    <title>Listado - POSTULANDO</title>
    <style>
        @page {
            size: A4;
            margin: 15mm 10mm;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 11px;
            line-height: 1.4;
            color: #000;
        }
        
        .listado-preview-header {
            text-align: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #333;
        }
        
        .listado-preview-header h2 {
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .listado-preview-header p {
            font-size: 11px;
            margin: 2px 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        
        th, td {
            border: 1px solid #333;
            padding: 5px 8px;
            text-align: left;
            font-size: 10px;
        }
        
        th {
            background-color: #e0e0e0;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .footer {
            margin-top: 30px;
            page-break-inside: avoid;
        }
        
        /* Salto de página para listados por programa */
        h3 {
            font-size: 13px;
            padding: 8px;
            background: #e0e0e0;
            margin-top: 20px;
            margin-bottom: 10px;
            page-break-before: always;
        }
        
        h3:first-of-type {
            page-break-before: avoid;
        }
        
        @media print {
            body {
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }
            
            .no-print {
                display: none !important;
            }
        }
    </style>
</head>
<body>
    ${preview.innerHTML}
</body>
</html>`);
    w.document.close();
    
    // Esperar a que cargue y luego imprimir
    setTimeout(() => {
        w.print();
    }, 250);
}

// ============================================================
// UTILIDADES
// ============================================================

async function actualizarContadores() {
    try {
        const data = await apiGet('/admin/api/stats');
        ['footerPostulantes', 'footerAulas', 'footerProfesores'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = data[id.replace('footer', 'total_').toLowerCase()] || 0;
        });
    } catch (e) { console.error(e); }
}

function cerrarModal(id) {
    document.getElementById(id)?.classList.remove('active');
}

function descargarPlantilla(tipo) {
    window.location.href = `/admin/api/plantillas/${tipo}`;
}

// ============================================================
// INICIALIZACIÓN
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    
    document.addEventListener('tabChanged', (e) => {
        const tab = e.detail.tabId;
        if (tab === 'tab-postulantes') cargarPostulantes();
        else if (tab === 'tab-aulas') { cargarAulas(); actualizarPreviewCodigo(); }
        else if (tab === 'tab-profesores') cargarProfesores();
    });
    
    cargarPostulantes();
    actualizarContadores();
    
    // Filtros con debounce
    ['filtroDni', 'filtroApellidos'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', debounce(filtrarPostulantes, 300));
    });
    
    document.getElementById('prefijoAula')?.addEventListener('change', actualizarPreviewCodigo);
});


/* ============================================================
   CONTROL DE ASISTENCIA - DASHBOARD COORDINADOR
   static/js/admin/dashboard_coordinador.js 
   ============================================================ */  
// ============================================================================
// GESTIÓN DE ASISTENCIA
// ============================================================================

/**
 * Carga las aulas disponibles en el selector de asistencia
 */
async function cargarAulasAsistencia() {
    console.log('📥 Cargando aulas para asistencia...');
    
    try {
        const proceso = document.querySelector('[name="proceso_admision"]')?.value || '2025-2';
        const response = await fetch(`/api/aulas-con-asignaciones?proceso=${proceso}&formato=simple`);
        const aulas = await response.json();
        
        const select = document.getElementById('aulaAsistencia');
        if (!select) return;
        
        select.innerHTML = '<option value="">-- Seleccione un aula --</option>';
        
        aulas.forEach(aula => {
            const option = document.createElement('option');
            option.value = aula.id;
            option.textContent = `${aula.codigo} - ${aula.nombre || 'Sin nombre'} (${aula.total} postulantes)`;
            select.appendChild(option);
        });
        
        console.log(`✅ ${aulas.length} aulas cargadas`);
        
    } catch (error) {
        console.error('❌ Error cargando aulas:', error);
        alert('Error al cargar aulas: ' + error.message);
    }
}

/**
 * Carga los postulantes del aula seleccionada
 */
async function cargarPostulantesAsistencia() {
    console.log('📥 Cargando postulantes para asistencia...');
    
    const select = document.getElementById('aulaAsistencia');
    const aulaId = select.value;
    
    if (!aulaId) {
        document.getElementById('contenedorAsistencia').classList.add('hidden');
        return;
    }
    
    const contenedor = document.getElementById('contenedorAsistencia');
    const infoAula = document.getElementById('infoAulaAsistencia');
    const lista = document.getElementById('listaPostulantesAsistencia');
    
    // Mostrar loading
    contenedor.classList.remove('hidden');
    lista.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="spinner"></div>
            <p style="margin-top: 10px;">Cargando postulantes...</p>
        </div>
    `;
    
    try {
        const proceso = document.querySelector('[name="proceso_admision"]')?.value || '2025-2';
        const response = await fetch(`/api/obtener-postulantes-aula/${aulaId}?proceso=${proceso}`);
        
        if (!response.ok) {
            throw new Error('Error al obtener postulantes');
        }
        
        const data = await response.json();
        
        console.log('✅ Postulantes recibidos:', data.total_postulantes);
        
        // Mostrar info del aula
        let infoHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
                <div style="background: #fff; padding: 12px; border-radius: 8px; border-left: 4px solid var(--primary-color);">
                    <strong>🏫 Aula:</strong><br>${data.aula.codigo} - ${data.aula.nombre}
                </div>
                <div style="background: #fff; padding: 12px; border-radius: 8px; border-left: 4px solid #28a745;">
                    <strong>👥 Total postulantes:</strong><br>${data.total_postulantes}
                </div>
                <div style="background: #fff; padding: 12px; border-radius: 8px; border-left: 4px solid ${data.asistencia_registrada ? '#28a745' : '#ffc107'};">
                    <strong>📊 Estado:</strong><br>${data.asistencia_registrada ? '✅ Ya registrada' : '⏳ Sin registrar'}
                </div>
            </div>
        `;
        
        if (data.asistencia_registrada) {
            infoHTML += `
                <div style="margin-top: 12px; padding: 12px; background: #d1ecf1; border-radius: 8px; border-left: 4px solid #17a2b8;">
                    <strong>ℹ️ Última actualización:</strong> ${new Date(data.hora_ultimo_registro).toLocaleString('es-PE')} 
                    por ${data.registrado_por}
                </div>
            `;
        }
        
        infoAula.innerHTML = infoHTML;
        
        // Generar lista de postulantes
        let listaHTML = `
            <!-- Alerta fija -->
            <div class="alerta-marcar">
                ⚠️ MARQUE SOLO LOS POSTULANTES AUSENTES
            </div>
            
            <!-- Contador dinámico de ausentes -->
            <div class="contador-ausentes" id="contadorAusentes" style="display: none;">
                <div class="numero" id="numeroAusentes">0</div>
                <div class="texto">
                    POSTULANTES AUSENTES<br>
                    <small style="opacity: 0.9;">Marcados con checkbox</small>
                </div>
            </div>
            
            <!-- Grid de postulantes -->
            <div class="grid-postulantes">
        `;
        
        data.postulantes.forEach(p => {
            const checked = !p.asistio ? 'checked' : '';
            const clase = !p.asistio ? 'ausente' : '';
            
            listaHTML += `
                <label class="postulante-checkbox ${clase}" data-dni="${p.dni}">
                    <input type="checkbox" ${checked} onchange="toggleAusente(this, '${p.dni}')">
                    <span class="orden-badge">${p.orden.toString().padStart(2, '0')}</span>
                    <span class="postulante-info">
                        <strong>${p.apellido_paterno} ${p.apellido_materno}</strong>
                        <small>${p.nombres}</small>
                        <small>DNI: ${p.dni}</small>
                    </span>
                    <span class="estado-badge">${!p.asistio ? '❌ AUSENTE' : '✅ PRESENTE'}</span>
                </label>
            `;
        });
        
        listaHTML += '</div>';
        lista.innerHTML = listaHTML;
        
        // Actualizar contador inicial
        actualizarContadorAusentes();
        
    } catch (error) {
        console.error('❌ Error:', error);
        lista.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #dc3545;">
                <h4>❌ Error al cargar postulantes</h4>
                <p>${error.message}</p>
                <button class="btn btn-outline" onclick="cargarPostulantesAsistencia()">🔄 Reintentar</button>
            </div>
        `;
    }
}

/**
 * Actualiza el contador de ausentes
 */
function actualizarContadorAusentes() {
    const checkboxes = document.querySelectorAll('#listaPostulantesAsistencia input[type="checkbox"]:checked');
    const contador = document.getElementById('contadorAusentes');
    const numero = document.getElementById('numeroAusentes');
    
    if (!contador || !numero) return;
    
    const totalAusentes = checkboxes.length;
    
    numero.textContent = totalAusentes;
    
    if (totalAusentes > 0) {
        contador.style.display = 'flex';
    } else {
        contador.style.display = 'none';
    }
}

/**
 * Toggle estado de asistencia de un postulante
 */
function toggleAusente(checkbox, dni) {
    const label = checkbox.closest('.postulante-checkbox');
    const estadoBadge = label.querySelector('.estado-badge');
    
    if (checkbox.checked) {
        // Marcado como AUSENTE
        label.classList.add('ausente');
        estadoBadge.textContent = '❌ AUSENTE';
    } else {
        // Marcado como PRESENTE
        label.classList.remove('ausente');
        estadoBadge.textContent = '✅ PRESENTE';
    }
    
    // Actualizar contador
    actualizarContadorAusentes();
}

/**
 * Marca todos como presentes
 */
function marcarTodosPresentes() {
    const checkboxes = document.querySelectorAll('#listaPostulantesAsistencia input[type="checkbox"]');
    
    checkboxes.forEach(checkbox => {
        if (checkbox.checked) {
            checkbox.checked = false;
            toggleAusente(checkbox, checkbox.closest('.postulante-checkbox').dataset.dni);
        }
    });
    
    alert('✅ Todos marcados como PRESENTES');
}

/**
 * Guarda la asistencia
 */
async function guardarAsistencia() {
    const select = document.getElementById('aulaAsistencia');
    const aulaId = select.value;
    
    if (!aulaId) {
        alert('Debe seleccionar un aula');
        return;
    }
    
    // Obtener DNIs de ausentes (checkboxes marcados)
    const checkboxes = document.querySelectorAll('#listaPostulantesAsistencia input[type="checkbox"]:checked');
    const ausentesDNI = Array.from(checkboxes).map(cb => {
        return cb.closest('.postulante-checkbox').dataset.dni;
    });
    
    const totalPostulantes = document.querySelectorAll('#listaPostulantesAsistencia .postulante-checkbox').length;
    const totalAusentes = ausentesDNI.length;
    const totalPresentes = totalPostulantes - totalAusentes;
    
    // Confirmación
    const mensaje = `¿CONFIRMAR REGISTRO DE ASISTENCIA?

📊 Resumen:
- Total postulantes: ${totalPostulantes}
- Presentes: ${totalPresentes}
- Ausentes: ${totalAusentes}

Esta acción actualizará el registro en la base de datos.`;
    
    if (!confirm(mensaje)) {
        return;
    }
    
    // Obtener usuario actual (desde el header)
    const usuarioElement = document.querySelector('.user-badge');
    const usuarioNombre = usuarioElement ? usuarioElement.textContent.replace('👤 ', '').trim() : 'Sistema';
    
    try {
        const proceso = document.querySelector('[name="proceso_admision"]')?.value || '2025-2';
        
        const response = await fetch('/api/registrar-asistencia', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                aula_id: parseInt(aulaId),
                proceso_admision: proceso,
                ausentes_dni: ausentesDNI,
                registrado_por: usuarioNombre
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al guardar asistencia');
        }
        
        const data = await response.json();
        
        console.log('✅ Asistencia guardada:', data);
        
        alert(`✅ ASISTENCIA REGISTRADA CORRECTAMENTE

📊 Resumen:
- Aula: ${data.aula_codigo}
- Total: ${data.total_postulantes}
- Presentes: ${data.total_presentes}
- Ausentes: ${data.total_ausentes}
- Registrado por: ${data.registrado_por}
- Hora: ${new Date(data.hora_registro).toLocaleString('es-PE')}`);
        
        // Recargar la lista para mostrar estado actualizado
        await cargarPostulantesAsistencia();
        
    } catch (error) {
        console.error('❌ Error:', error);
        alert('❌ Error al guardar asistencia:\n\n' + error.message);
    }
}

/**
 * Inicializar pestaña de asistencia
 */
function inicializarAsistencia() {
    // Cargar aulas cuando se abre la pestaña
    const tabAsistencia = document.querySelector('[data-tab="tab-asistencia"]');
    if (tabAsistencia) {
        tabAsistencia.addEventListener('click', function() {
            // Solo cargar si el select está vacío
            const select = document.getElementById('aulaAsistencia');
            if (select && select.options.length <= 1) {
                cargarAulasAsistencia();
            }
        });
    }
}

// Inicializar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarAsistencia);
} else {
    inicializarAsistencia();
}