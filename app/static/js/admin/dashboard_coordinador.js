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

function seleccionarTipoListado(tipo) {
    document.querySelectorAll('.listado-option').forEach(o => o.classList.remove('selected'));
    document.querySelector(`[data-listado="${tipo}"]`)?.classList.add('selected');
    
    // Mostrar/ocultar selector de aula
    const configAula = document.getElementById('config-por-aula');
    if (configAula) {
        if (tipo === 'por-aula') {
            configAula.classList.remove('hidden');
        } else {
            configAula.classList.add('hidden');
        }
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