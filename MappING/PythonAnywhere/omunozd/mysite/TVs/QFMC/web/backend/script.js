// Browser script: fetch data and populate the editable event card.
// Uses the IDs added in the HTML (`event-day`, `event-type`, `event-title`, etc.).

const TIEMPO_IMAGEN = 10000; //ms
const MAX_LEN_BEFORE_SHRINK = 26; //chars
const DATA_FILEPATH = "QFMC/web/backend/data/QFMC_data.json";
const DEFAULT_EVENT_DURATION_MINUTES = 70;
const EVENT_TIME_ZONE = 'America/Santiago';

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
        if (!raw) return { raw: '', fecha: '', hora: '' };
        if (!raw.includes('T')) return { raw, fecha: raw, hora: '' };
        const [fecha, tiempo] = raw.split('T');
        const hora = tiempo.substring(0, 5); // HH:MM
        return { raw, fecha, hora };
    }

    return {
        nombre: n.properties?.Nombre?.title?.[0]?.text?.content || '',
        emoji: n.icon?.emoji || '',
        tipo: {
            nombre: n.properties?.Tipo?.select?.name || '',
            color: n.properties?.Tipo?.select?.color || ''
        },
        publico: n.properties?.["P\u00fablico"]?.checkbox === true,
        lugar: n.properties?.Lugar?.rich_text?.[0]?.text?.content || '',
        etiquetas: (n.properties?.Etiquetas?.multi_select || []).map(t => ({ nombre: t.name, color: t.color })),
        comentario: n.properties?.Comentario?.rich_text?.[0]?.text?.content || '',
        imagen: n.cover?.external?.url || n.cover?.file?.url || '',
        imagenTipo: n.cover?.type || '',
        fecha: {
            inicio: parseDate(startRaw),
            fin: parseDate(endRaw),
            todo_el_dia: !startRaw.includes('T')
        }
    };
}

function getZonedDateTime(fecha, hora = '00:00:00', timeZone = EVENT_TIME_ZONE) {
    if (!fecha) return null;
    const [year, month, day] = fecha.split('-').map(Number);
    const [hour, minute, second] = hora.split(':').map(Number);
    const utcGuess = new Date(Date.UTC(year, month - 1, day, hour, minute, second || 0));
    const parts = new Intl.DateTimeFormat('en-US', {
        timeZone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23'
    }).formatToParts(utcGuess).reduce((acc, part) => {
        acc[part.type] = part.value;
        return acc;
    }, {});
    const zonedAsUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
    const offset = zonedAsUtc - utcGuess.getTime();
    return new Date(utcGuess.getTime() - offset);
}

function parseLocalDate(fecha, endOfDay = false) {
    const date = getZonedDateTime(fecha, endOfDay ? '23:59:59' : '00:00:00');
    if (date && endOfDay) date.setMilliseconds(999);
    return date;
}

function hasExplicitTimeZone(raw) {
    return /([zZ]|[+-]\d{2}:?\d{2})$/.test(raw);
}

function parseTimedDate(datePart) {
    if (!datePart.raw?.includes('T')) return null;
    if (hasExplicitTimeZone(datePart.raw)) return new Date(datePart.raw);
    const [fecha, tiempo] = datePart.raw.split('T');
    return getZonedDateTime(fecha, tiempo.substring(0, 8));
}

function getEventStartDate(evento) {
    const inicio = evento.fecha.inicio;
    if (!inicio.fecha) return null;
    return inicio.raw?.includes('T') ? parseTimedDate(inicio) : parseLocalDate(inicio.fecha);
}

function getEventEndDate(evento) {
    const inicio = evento.fecha.inicio;
    const fin = evento.fecha.fin;

    if (!inicio.fecha) return null;

    if (fin.raw?.includes('T')) {
        return parseTimedDate(fin);
    }

    if (inicio.raw?.includes('T')) {
        const start = getEventStartDate(evento);
        if (!start) return null;
        return new Date(start.getTime() + DEFAULT_EVENT_DURATION_MINUTES * 60 * 1000);
    }

    return parseLocalDate(fin.fecha || inicio.fecha, true);
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

    // Normalizar eventos y filtrar los que ya terminaron
    let eventos = results.map(normalizeEvent);

    const ahora = new Date();

    // Mantener eventos hasta que terminen, incluyendo eventos del mismo dia.
    eventos = eventos.filter(evento => {
        const finEvento = getEventEndDate(evento);
        return evento.publico && finEvento && finEvento >= ahora;
    });

    // Ordenar eventos por fecha (mas proximos primero)
    eventos.sort((a, b) => {
        const fechaA = getEventStartDate(a);
        const fechaB = getEventStartDate(b);
        return fechaA - fechaB;
    });
    
    // Cache elementos DOM
    const elemDia = document.getElementById('event-day');
    const elemTipo = document.getElementById('event-type');
    const elemTitulo = document.getElementById('event-title');
    const elemHora = document.getElementById('event-time');
    const elemLugar = document.getElementById('event-location');
    const elemLugarChip = document.getElementById('event-location-chip');
    const elemComentario = document.getElementById('event-description');
    const elemEtiquetas = document.getElementById('event-tags');
    const elemImagen = document.getElementById('event-image');

    // Función para mostrar un evento
    async function mostrarEvento(evento) {
        // Primero cargar la imagen si existe
        if (elemImagen && evento.imagen) {
            const urlLimpia = evento.imagenTipo === 'file' ? evento.imagen : evento.imagen.split('?')[0];
            await new Promise((resolve) => {
                const img = new Image();
                img.onload = resolve;
                img.onerror = resolve; // Resolver incluso si hay error
                img.src = urlLimpia;
            });
            elemImagen.src = urlLimpia;
            elemImagen.hidden = false;
        } else if (elemImagen) {
            elemImagen.src = "../TV/QFMC/web/frontend/sources/carton.jpg"
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
        const lugar = (evento.lugar || '').trim();
        if (elemLugar) elemLugar.textContent = lugar;
        if (elemLugarChip) {
            elemLugarChip.hidden = !lugar;
            elemLugarChip.style.display = lugar ? 'inline-flex' : 'none';
        }

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
