from flask import Flask, make_response, send_file
from ics import Calendar, Event
import requests
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from mimetypes import guess_type
def now_time():
    """Devuelve la fecha y hora UTC actual para archivos generados y eventos de respaldo."""
    return datetime.now(timezone.utc)
import traceback

from mysite.TVs.QFMC import spotify
from mysite.notion_creds import HEADERS_TRINIP, DATABASES_IDS
from mysite.utils import printt

def get_content_type(file_path: str) -> str:
    """Devuelve el Content-Type HTTP de un archivo segun su extension."""
    
    mime_type, _ = guess_type(file_path)
    if mime_type:
        return mime_type if 'charset' in mime_type else f"{mime_type}; charset=utf-8"
    
    # Fallback para tipos comunes
    ext = os.path.splitext(file_path)[1].lower()
    content_types = {
        '.html': 'text/html; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.js': 'application/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.svg': 'image/svg+xml',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.ico': 'image/x-icon',
        '.pdf': 'application/pdf',
        '.ttf': 'font/ttf',
        '.otf': 'font/otf',
        '.woff': 'font/woff',
        '.woff2': 'font/woff2',
    }
    return content_types.get(ext, 'application/octet-stream')

CALENDAR_FOLDER = os.path.join("mysite", "calendars")
SANTIAGO_TZ = ZoneInfo("America/Santiago")

app = Flask(__name__)


def calendar_file_path(filename: str) -> str:
    """Devuelve la ruta absoluta de un archivo ICS dentro de la carpeta de calendarios."""
    os.makedirs(CALENDAR_FOLDER, exist_ok=True)
    return os.path.abspath(os.path.join(CALENDAR_FOLDER, filename))


def calendar_folder_files() -> list[str]:
    """Lista los archivos disponibles en la carpeta de calendarios."""
    os.makedirs(CALENDAR_FOLDER, exist_ok=True)
    return os.listdir(CALENDAR_FOLDER)


def qfmc_event_week_filter(today=None) -> str:
    """Devuelve el filtro semanal de Notion para QFMC; en fines de semana usa la proxima semana."""
    if today is None:
        today = datetime.now(SANTIAGO_TZ).date()

    return "next_week" if today.weekday() >= 5 else "this_week"


def get_notion_icon_text(notion_icon: dict | None) -> str:
    """Devuelve el emoji de un icono de Notion, o texto vacio si el icono es archivo o link."""
    if not notion_icon or notion_icon.get("type") != "emoji":
        return ""

    return f"{notion_icon.get('emoji', '')} "


def calendar_start_of_year_filter(today=None) -> dict:
    """Devuelve el filtro de Notion para incluir eventos desde el inicio del año actual."""
    if today is None:
        today = datetime.now(SANTIAGO_TZ).date()

    return {
        "property": "Fecha",
        "date": {
            "on_or_after": f"{today.year}-01-01"
        }
    }


def with_calendar_base_filter(payload: dict | None = None) -> dict:
    """Combina un payload de Notion con el filtro base del calendario anual."""
    payload = dict(payload or {})
    base_filter = calendar_start_of_year_filter()
    existing_filter = payload.get("filter")

    payload["filter"] = {
        "and": [base_filter, existing_filter] if existing_filter else [base_filter]
    }

    return payload


def get_notion_data(payload: dict | None = None, filename: str = "calendar.ics"):
    """Obtiene actividades desde Notion y escribe un calendario publico de Ingenieria en formato ICS."""
    url = f"https://api.notion.com/v1/databases/{DATABASES_IDS['actividades_ing']}/query"
    data = []
    run = True
    payload = with_calendar_base_filter(payload)
    payload["page_size"] = 100

    while run:
        response = requests.post(url, headers=HEADERS_TRINIP, json=payload)

        data.extend(response.json().get("results", []))

        run = response.json().get("has_more", False)

        if response.json().get("next_cursor", None):
            payload["start_cursor"] = response.json()["next_cursor"]

    cal = Calendar()
    cal.events = set()

    cal_name = "Actividades en Ingeniería UC | CAi💛"

    for n in data:

        if n["properties"]["Fecha"]["date"] and n["properties"]["Público"]["checkbox"]:
            event = Event()

            event.begin = n["properties"]["Fecha"]["date"]["start"]
            event.end = n["properties"]["Fecha"]["date"]["end"]

            if "T" not in n["properties"]["Fecha"]["date"]["start"]:
                event.make_all_day()

            else:
                if not n["properties"]["Fecha"]["date"]["end"]:
                    event.duration = {"hours": 1, "minutes": 10}

            icon = get_notion_icon_text(n.get("icon"))

            name = n["properties"]["Nombre"]["title"][0]["text"]["content"] if n["properties"]["Nombre"] and len(
                n["properties"]["Nombre"]["title"]) > 0 else ""

            # type_ = n["properties"]["Tipo"]["select"]["name"] if n["properties"]["Tipo"]["select"] else ""

            even_name = icon + name  # + (" - " + type_ if type_ else "")
            event.name = even_name

            event.classification = n["properties"]["Tipo"]["select"]["name"] if n["properties"]["Tipo"]["select"] else ""

            areas = list(
                map(lambda x: x["name"], n["properties"]["Áreas"]["multi_select"]))
            inscripciones = n["properties"]["Inscripciones"]["url"] if n["properties"]["Inscripciones"]["url"] else ""
            link_info = n["properties"]["Info"]["url"] if n["properties"]["Info"]["url"] else ""
            organizadores = list(
                map(lambda x: x["name"], n["properties"]["Organiza"]["multi_select"]))
            targets = list(
                map(lambda x: x["name"], n["properties"]["Público Objetivo"]["multi_select"]))
            comentario = n["properties"]["Comentario"]["rich_text"][0]["plain_text"] if n["properties"]["Comentario"]["rich_text"] else ""
            lugar = n["properties"]["Lugar"]["rich_text"][0]["plain_text"] if n["properties"]["Lugar"]["rich_text"] else ""

            event.location = lugar
            event.categories = areas

            lineas_desc = [
                f"{comentario}\n"
                f"Inscripciones: {inscripciones}" if inscripciones else "",
                f"Más información: {link_info}" if link_info else "",
                f"Organizan: {", ".join(organizadores)}",
                f"Público objetivo: {", ".join(targets)}",
                f"Áreas de Interés: {", ".join(areas)}"                
            ]
            event.description = "\n".join(
                filter(lambda x: x != "", lineas_desc))

            cal.events.add(event)

    ics_ser = cal.serialize().replace(
        "BEGIN:VCALENDAR",
        f"BEGIN:VCALENDAR\nX-WR-CALNAME:{cal_name}\nX-WR-TIMEZONE:America/Santiago"
    )

    with open(calendar_file_path(filename), "w", encoding="utf-8") as f:
        f.write(ics_ser.replace("\r\n", "\n"))


def calendar_error(error):
    """Construye un calendario ICS breve con un evento que describe un error de actualizacion."""
    cal = Calendar()

    event = Event(
        name="❌ Error actualizando calendario",
        begin=now_time(),
        end=now_time() + timedelta(minutes=5),
        description=str(error)
    )

    cal.events.add(event)

    return cal, "error_file"


def save_file(cal, name):
    """Serializa un calendario ICS en la misma ruta que usa el servidor local de tests.py."""
    with open(calendar_file_path(f"{name}.ics"), "w", encoding="utf-8") as f:
        f.write(cal.serialize().replace("\r\n", "\n"))


@app.route('/')
def hello_world():
    """Sirve una pagina minima que dirige a visitantes al Instagram del CAi."""
    return 'Si buscas más información, visita nuestro <a href="instagram.com/caipuc">instagram</a>'


@app.route("/calendar/ing", methods=['GET'])
def return_calendar():
    """Actualiza y devuelve el calendario completo de actividades publicas de Ingenieria como ICS."""

    get_notion_data()

    try:
        file_path = calendar_file_path("calendar.ics")
        if os.path.isfile(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return make_response(f"File calendar.ics not found. With {file_path} {calendar_folder_files()}", 404)
    except Exception as e:
        return make_response(f"Error: {str(e)}", 500)


@app.route("/calendar/ing/<string:filtros_str>", methods=['GET'])
def return_calendar_filtrado(filtros_str: str):
    """Devuelve un calendario ICS filtrado por codigos URL de areas, publicos u organizadores."""

    ID_AREAS = {
        "INN": "Innovación",
        "VID": "Vida Universitaria",
        "SB": "Salud y Bienestar",
        "IIEE": "IIEE",
        "RP": "Rol Púlbico",
        "DOC": "Docencia",
        "DIS": "Disidencias",
        "COM": "Comunidad",
        "SUS": "Sustentabilidad",
        "FEM": "Feminismo",
        "INV": "Investigación y Postgrado",
        "COM": "Comunicaciones",
        "ACA": "Académico",
        "UP": "Utilidad Pública",
        "DEP": "Deportes"
    }

    FILTROS_URL = {
        area_key: {
            "property": "Áreas",
            "multi_select": {"contains": area_name}
        }
        for area_key, area_name in ID_AREAS.items()
    }

    ID_PUBLICOS = {
        "PRE": "Pregrado",
        "POST": "Postgrado",

        "GRA": "Gratuidad",
        "TEI": "Talento e Inclusión",
        "NACE": "NACE",

        "MUJ": "Mujeres",
        "DEPTA": "Deportista",
        "INI": "Iniciativa",

        "BIO": "Major Biológica",
        "CIV": "Major Civil",
        "ELE": "Major Eléctrica",
        "MEC": "Major Mecánica",
        "AMB": "Major Ambiental",
        "MIN": "Major Minería",
        "CON": "Major Construcción",
        "ARQ": "Major Arquitectura",
        "MED": "Major Biomed",
        "TRA": "Major Transporte"
    }

    FILTROS_URL.update({
        publico_key: {
            "property": "Público Objetivo",
            "multi_select": {"contains": publico_name}
        }
        for publico_key, publico_name in ID_PUBLICOS.items()
    })

    ID_ORGANIZADORES = {
        "CAI": "CAi",
        "ESC": "Escuela",
        "ODOC": "ODOC",
        "TUT": "Tutores",
        "GOING": "GOing",
        "PAS": "Pastoral",
        "MJL": "Major League",
        "CA": "CA",
        "CAP": "CAP",
        "UC": "UC",
        "DII": "DII",
        "UNT": "UNITE",
        "DCDI": "DCDI",
        "RAIZ": "La Raíz",
        "REH": "Reintegrando Humedales",
        "CERRNN": "Centro de Estudiantes de Recursos Naturales",
        "PDI": "Plan Deportivo",
        "CET": "Capítulo de Transporte",
        "ITA": "Itaú",
        "BCH": "Banco de Chile",
        "BCI": "BCI"
    }

    FILTROS_URL.update({
        org_key: {
            "property": "Organiza",
            "multi_select": {"contains": org_name}
        }
        for org_key, org_name in ID_ORGANIZADORES.items()
    })

    ids_filtros = filtros_str.split("&")
    filtros, ids_invalidos = [], []

    for id_filtro in ids_filtros:
        try:
            filtros.append(FILTROS_URL[id_filtro])
        except KeyError:
            ids_invalidos.append(id_filtro)

    if ids_invalidos:
        print(f"Filtros no reconocidos: {" ,".join(ids_invalidos)}")
        return make_response(f"Filtro no reconocidos: {" ,".join(ids_invalidos)}", 400)

    filename = "cal-filtr_" + str(now_time())[:-6].replace(" ", "_") + ".ics"
    get_notion_data(payload={"filter": {"or": filtros}}, filename=filename)

    try:
        file_path = calendar_file_path(filename)
        if os.path.isfile(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return make_response(f"File {filename} not found. With {file_path} {calendar_folder_files()}", 404)
    except Exception as e:
        return make_response(f"Error: {str(e)}", 500)

@app.route("/TV/assets/<path:filepath>", methods=['GET'])
def TV_assets(filepath: str):
    """Sirve assets del frontend QFMC, como fuentes locales, desde una ruta URL estable."""
    # Assets compartidos por el display QFMC, usando rutas absolutas estables desde CSS.
    abs_file_path = os.path.abspath(os.path.join("mysite", "TVs", "QFMC", "web", "frontend", "assets", filepath))
    abs_assets_path = os.path.abspath(os.path.join("mysite", "TVs", "QFMC", "web", "frontend", "assets"))

    if not abs_file_path.startswith(abs_assets_path):
        return make_response("Acceso denegado", 403)

    if not os.path.isfile(abs_file_path):
        return make_response(f"Asset no encontrado: {filepath}", 404)

    try:
        return send_file(abs_file_path, mimetype=get_content_type(abs_file_path))
    except Exception as e:
        return make_response(f"Error sirviendo asset: {str(e)}", 500)


@app.route("/TV/<path:filepath>", methods=['GET'])
def TVs(filepath: str):
    """Sirve archivos de displays TV y actualiza datos de QFMC antes de devolver su frontend."""
    # Actualizar desde Notion si se pregunta por QFMC
    if filepath in ["QFMC_hor.html","QFMC"]:
        try:
            week_filter = qfmc_event_week_filter()

            # Body para llamar a API de Notion - eventos de esta semana o la próxima si es fin de semana
            payload = {
                "page_size": 100,
                "filter": {
                    "and": [
                        {
                            "property": "Fecha",
                            "date": {
                                week_filter: {}
                            }
                        },
                        {
                            "property": "P\u00fablico",
                            "checkbox": {
                                "equals": True
                            }
                        }
                    ]
                }
            }
            
            # Llamar a Notion API
            url = f"https://api.notion.com/v1/databases/{DATABASES_IDS['actividades_ing']}/query"
            response = requests.post(url, headers=HEADERS_TRINIP, json=payload)
            
            if response.status_code != 200:
                return make_response(f"Error llamando a Notion API: {response.status_code} - {response.text}", 500)
            
            # Guardar los datos en web/backend/data
            data = response.json()
            data_file_path = os.path.join("mysite","TVs","QFMC","web","backend","data","QFMC_data.json")
            os.makedirs(os.path.dirname(data_file_path), exist_ok=True)

            import json
            with open(data_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Datos de Notion actualizados en {data_file_path}")
            
            filepath = os.path.join("QFMC","web","frontend","index.html")
                
        except Exception as e:
            traceback.print_exc()
            print("")
            return make_response(f"Error al actualizar datos de Notion: {str(e)}\n{str(e.__traceback__)}", 500)
    
    elif filepath == "cancion":
        folderpath = os.path.join("QFMC","Cancion_del_dia","spotify_codes")

        filepath = os.path.join(
            "QFMC","Cancion_del_dia","spotify_codes","default.svg")

        files = os.listdir(os.path.join("mysite","TVs",folderpath))
        today_str = datetime.today().strftime("%d_%m_%y")

        for file in files:
            if today_str in file and not file.endswith(".bak"):
                filepath = os.path.join(folderpath,file)
                break

    elif filepath == "actualizar_codigos_spotify":
        try:
            spotify.importar_programacion_notion()
        except Exception as e:
            Warning("ERROR al actualizar códigos spotify")
            traceback.print_exc()
            return make_response(f"Error al actualizar los códigos de spotify. Error interno: <br><p>{e}</p>", 500)
        else:
            printt("Códigos actualizados desde Notion.")
            return make_response("Códigos Actualizados. Revise el código de hoy <a href='https://omunozd.pythonanywhere.com/TV/cancion'>aquí</a>.",200)

    # Path del archivo solicitado
    abs_file_path = os.path.abspath(os.path.join("mysite","TVs", filepath))
    abs_tvs_path = os.path.abspath(os.path.join("mysite","TVs"))
    
    # Validar que no haya path traversal
    if not abs_file_path.startswith(abs_tvs_path):
        return make_response("Acceso denegado", 403)
    
    # Verificar que el archivo existe
    if not os.path.isfile(abs_file_path):
        return make_response(f"Archivo no encontrado: {filepath}", 404)
    
    # Servir el archivo con content-type correcto
    try:
        return send_file(abs_file_path, mimetype=get_content_type(abs_file_path))
    except Exception as e:
        return make_response(f"Error sirviendo archivo: {str(e)}", 500)  


spotify.guardar_codigo_spotify(
        "https://open.spotify.com/intl-es/track/4Qs3OEgzBPGPmRR5QJ0UIs", # Mi Equilibrio Espiritual
        tipo_archivo=".svg",
        filename="default",
        folderpath= os.path.join(
            "mysite",
            "TVs",
            "QFMC",
            "Cancion_del_dia",
            "spotify_codes"
        )
    )
