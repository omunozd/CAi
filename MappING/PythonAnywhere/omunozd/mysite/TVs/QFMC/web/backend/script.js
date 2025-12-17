// Browser script: fetch data and populate the editable event card.
// Uses the IDs added in the HTML (`event-day`, `event-type`, `event-title`, etc.).

const TIEMPO_IMAGEN = 10000; //ms
const MAX_LEN_BEFORE_SHRINK = 26; //chars
const DATA_FILEPATH = "QFMC/web/backend/data/QFMC_data.json";

// Función para obtener el día de la semana en español
function getDiaSemana(fecha) {
    if (!fecha) return '';
    const dias = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
    const [year, month, day] = fecha.split('-').map(Number);
    const date = new Date(year, month - 1, day);
    return dias[date.getDay()];
}

// Formatea y normaliza la estructura de cada evento desde la respuesta de Notion
function normalizeEvent(n) {
    const startRaw = n.properties?.Fecha?.date?.start || '';
    const endRaw = n.properties?.Fecha?.date?.end || '';
    function parseDate(raw) {
        if (!raw) return { fecha: '', hora: '' };
        if (!raw.includes('T')) return { fecha: raw, hora: '' };
        const [fecha, tiempo] = raw.split('T');
        const hora = tiempo.substring(0, 5); // HH:MM
        return { fecha, hora };
    }

    return {
        nombre: n.properties?.Nombre?.title?.[0]?.text?.content || '',
        emoji: n.icon?.emoji || '',
        tipo: {
            nombre: n.properties?.Tipo?.select?.name || '',
            color: n.properties?.Tipo?.select?.color || ''
        },
        lugar: n.properties?.Lugar?.rich_text?.[0]?.text?.content || '',
        etiquetas: (n.properties?.Etiquetas?.multi_select || []).map(t => ({ nombre: t.name, color: t.color })),
        comentario: n.properties?.Comentario?.rich_text?.[0]?.text?.content || '',
        imagen: n.cover?.external?.url || '',
        fecha: {
            inicio: parseDate(startRaw),
            fin: parseDate(endRaw),
            todo_el_dia: !startRaw.includes('T')
        }
    };
}

function setupEditableElements() {
    const editableElements = document.querySelectorAll('[contenteditable="true"]');
    editableElements.forEach(element => {
        element.addEventListener('blur', () => {
            element.textContent = element.textContent.trim();
            if (element.textContent === '') {
                if (element.id === 'event-day' || element.classList.contains('day')) element.textContent = 'Lunes';
                else if (element.id === 'event-type' || element.classList.contains('chip-type')) element.textContent = 'Charla';
                else if (element.id === 'event-title' || element.classList.contains('title')) element.textContent = 'Evento de prueba';
                else if (element.classList.contains('chip')) {
                    const icon = element.querySelector('.icon')?.textContent;
                    if (icon === '🕒') element.innerHTML = '<span class="icon">🕒</span> 13:00 – 14:30';
                    else if (icon === '📍') element.innerHTML = '<span class="icon">📍</span> Patio de Ing.';
                    else element.textContent = 'Chip';
                }
            }
        });
        element.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); element.blur(); }
        });
    });
}

function createTagElement(tag, index) {
    const span = document.createElement('span');
    span.className = 'chip';
    span.id = `tag-${index+1}`;
    span.setAttribute('contenteditable', 'true');
    span.setAttribute('spellcheck', 'false');
    span.textContent = tag.nombre;
    // Set background color from tag.color (Notion color names)
    if (tag.color) {
        // Map Notion color names to CSS colors if needed
        const notionColorMap = {
            'default': '#e0e0e0',
            'gray': '#bdbdbd',
            'brown': '#a1887f',
            'orange': '#ffb74d',
            'yellow': '#fff176',
            'green': '#81c784',
            'blue': '#64b5f6',
            'purple': '#ba68c8',
            'pink': '#bc4d72ff',
            'red': '#a35151ff'
        };
        span.style.backgroundColor = notionColorMap[tag.color] || tag.color;
    }
    return span;
}

async function loadAndPopulate() {
    // Try fetching the DATA_FILEPATH file relative to this HTML page.
    let data;
    try {
        const res = await fetch(DATA_FILEPATH);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        data = await res.json();
        console.log("Data cargada OK.")
    } catch (err) {
        console.warn('No se pudo cargar los datos vía fetch. Asegúrate de servir los archivos por HTTP. Error:', err);
        // setupEditableElements();
        return;
    }

    const results = data.results || [];
    if (results.length === 0) { 
        // setupEditableElements(); 
        return; 
    }

    // Normalizar eventos y filtrar por fecha futura
    let eventos = results.map(normalizeEvent);
    
    const ahora = new Date();
    ahora.setHours(0, 0, 0, 0); // Comparar por día completo
    
    // Filtrar solo eventos que son después de hoy
    eventos = eventos.filter(evento => {
        if (!evento.fecha.inicio.fecha) return false;
        const fechaEvento = new Date(evento.fecha.inicio.fecha);
        return fechaEvento >= ahora;
    });
    
    // Ordenar eventos por fecha (más próximos primero)
    eventos.sort((a, b) => {
        const fechaA = new Date(a.fecha.inicio.fecha);
        const fechaB = new Date(b.fecha.inicio.fecha);
        return fechaA - fechaB;
    });
    
    // Cache elementos DOM
    const elemDia = document.getElementById('event-day');
    const elemTipo = document.getElementById('event-type');
    const elemTitulo = document.getElementById('event-title');
    const elemHora = document.getElementById('event-time');
    const elemLugar = document.getElementById('event-location');
    const elemComentario = document.getElementById('event-description');
    const elemEtiquetas = document.getElementById('event-tags');
    const elemImagen = document.getElementById('event-image');

    // Función para mostrar un evento
    async function mostrarEvento(evento) {
        // Primero cargar la imagen si existe
        if (elemImagen && evento.imagen) {
            const urlLimpia = evento.imagen.split('?')[0];
            await new Promise((resolve) => {
                const img = new Image();
                img.onload = resolve;
                img.onerror = resolve; // Resolver incluso si hay error
                img.src = urlLimpia;
            });
            elemImagen.src = urlLimpia;
            elemImagen.hidden = false;
        } else if (elemImagen) {
            elemImagen.src = "../frontend/sources/carton.jpg"
            elemImagen.hidden = true;
        }

        // Luego mostrar la información
        // Tipo de evento
        if (elemTipo) elemTipo.textContent = evento.tipo.nombre || 'Sin tipo';

        // Título con emoji
        if (elemTitulo) {
            const tituloCompleto = `${evento.emoji ? evento.emoji + ' ' : ''}${evento.nombre}`;
            elemTitulo.textContent = tituloCompleto;
            elemTitulo.style.fontSize = tituloCompleto.length > MAX_LEN_BEFORE_SHRINK ? '6rem' : '';
        }

        // Lugar
        if (elemLugar) elemLugar.textContent = evento.lugar || 'Sin ubicación';

        // Comentario
        if (elemComentario) {
            elemComentario.textContent = evento.comentario || '';
            elemComentario.hidden = !evento.comentario;
        }

        // Fecha y hora
        if (elemDia) {
            elemDia.textContent = getDiaSemana(evento.fecha.inicio.fecha) || 'Sin fecha';
        }

        if (elemHora) {
            if (evento.fecha.todo_el_dia || !evento.fecha.fin.fecha) {
                elemHora.textContent = 'Todo el día';
            }
            else if (evento.fecha.inicio.fecha !== evento.fecha.fin.fecha) {
                const inicio = evento.fecha.inicio.fecha.substring(8,10) + "/" + evento.fecha.inicio.fecha.substring(5,7);
                const fin = evento.fecha.fin.fecha.substring(8,10) + "/" + evento.fecha.fin.fecha.substring(5,7);
                elemHora.textContent = `${inicio} → ${fin}`;
            }
            else if (evento.fecha.inicio.hora) {
                let horario = evento.fecha.inicio.hora;
                if (evento.fecha.fin.hora) {
                    horario += ' - ' + evento.fecha.fin.hora;
                }
                elemHora.textContent = horario;
            }
        }

        // Etiquetas
        if (elemEtiquetas) {
            elemEtiquetas.innerHTML = '';
            evento.etiquetas.forEach((tag, i) => {
                const tagEl = createTagElement(tag, i);
                elemEtiquetas.appendChild(tagEl);
            });
        }
    }

    // Iniciar rotación de eventos
    if (eventos.length > 0) {
        let indiceActual = 0;
        mostrarEvento(eventos[indiceActual]);
        
        setInterval(() => {
            indiceActual = (indiceActual + 1) % eventos.length;
            mostrarEvento(eventos[indiceActual]);
        }, TIEMPO_IMAGEN);
    }

    // Hook editable behaviour after populating
    // setupEditableElements();
}

document.addEventListener('DOMContentLoaded', () => {
    loadAndPopulate();
    
    // Agregar listener al logo izquierdo para fullscreen
    const logoLeft = document.getElementById('logo-left');
    if (logoLeft) {
        logoLeft.style.cursor = 'pointer';
        logoLeft.addEventListener('click', () => {
            const frame = document.getElementById('event-frame');
            if (frame) {
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    frame.requestFullscreen().catch(err => {
                        console.error('Error al intentar fullscreen:', err);
                    });
                }
            }
        });
    }
});