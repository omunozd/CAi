import requests
import traceback
from datetime import datetime
from typing import NamedTuple
from threading import Thread, Lock, current_thread
import os

from mysite.TVs.QFMC.Cancion_del_dia.add_svg_bar_anim import add_bar_animations
from mysite.notion_creds import HEADERS_OSCAR_CAI, DATABASES_IDS
from mysite.utils import printt


def guardar_codigo_spotify(
        URI_or_URL: str,
        fecha: datetime | str | None = None,
        color_fondo: str = "fff8e8",
        color_barras: bool = False,
        ancho: int = 1000,
        tipo_archivo: str = ".svg",
        logo_QFMC: bool = True,
        folderpath: str = None,
        filename: str = None,
        nombre_cancion: str = ""):
    """
    Esta función genera y guarda el Spotify Code de la canción que se ingrese. Utiliza la API nativa
    de Spotify para obtener el código original, luego le cambia el logo. También funciona para playlists, 
    álbums, etc.

    Retorna el filepath del archivo donde se guardó.

    :param URI_or_URL: URL de spotify -https://open.spotify.com/track/...-, o bien, su URI: -spotify:track:...-
    :type URI_or_URL: str

    :param fecha: Fecha para la que se quiere programar la canción en formato dd_mm_yy. Es sólo para ponerlo
    en el nombre de archivo.
    :type fecha: datetime | str | None

    :param color_fondo: Color del fondo en RGB hexagesimal.
    :type color_fondo: str

    :param color_barras: True para barras blancas, False para barras negras.
    :type color_barras: bool

    :param ancho: Ancho del código en pixeles.
    :type ancho: int

    :param tipo_archivo: '.svg' o '.png'
    :type tipo_archivo: str

    :param logo_QFMC: True si se quiere reemplazar el logo de spotify por el de QFMC, sino, se deja el
    de Spotify.
    :type logo_QFMC: bool

    :param folderpath: Path de la carpeta donde se quiere guardar el código.
    :type folderpath: str

    :param filename: Nombre del archivo a guardar, en caso de querer personalizarlo.
    :type filename: str

    :param nombre_cancion: Si se incluye un nombre de canción, se agrega al final del nombre de archivo.
    :type nombre_cancion: str
    """

    folderpath = os.path.join("mysite", "TVs", "QFMC",
                              "Cancion_del_dia", "spotify_codes") if not folderpath else folderpath
    lock_escritura = Lock()

    if "http" in URI_or_URL:
        URL_data = URI_or_URL.split("/")
        URI = f"spotify:{URL_data[-2]}:{URL_data[-1].split("?")[0]}"
    elif "spotify:" in URI_or_URL:
        URI = URI_or_URL
    else:
        raise ValueError(f"URI o URL no reconocida: {URI_or_URL}")

    save_content_types = {
        "image/svg+xml": ".svg",
        "image/png": ".png"
    }

    if tipo_archivo not in save_content_types.values():
        raise ValueError(
            f"Tipo de archivo {tipo_archivo} no válido. Se aceptan: {" , ".join(save_content_types.values())}")

    url_base = "https://scannables.scdn.co/uri/plain/"
    parametros_url = [tipo_archivo[1:],
                      color_fondo,
                      "white" if color_barras else "black",
                      str(ancho),
                      URI]
    url = url_base + "/".join(parametros_url)

    try:
        response = requests.get(url)
    except:
        traceback.print_exc()
        printt("\nError al solicitar generación de código.")
        raise ConnectionError("Error HTTP: No se pudo realizar la solicitud.")

    else:
        if response.status_code != 200:
            raise Exception(
                f"Error ({response.status_code}) en la solicitud.\nGET: {url}")

        if isinstance(fecha, datetime):
            str_fecha = fecha.strftime("%d_%m_%y")
        elif type(fecha) == str:
            str_fecha = fecha
        else:
            str_fecha = datetime.today().strftime("%d_%m_%y")

        content_type = response.headers.get("content-type")

        if not filename:
            filename = f"QFMC_CDD_{str_fecha}{"_" + nombre_cancion if nombre_cancion else ""}{save_content_types[content_type]}"
        elif filename and "." in filename:
            idx = filename.index(".")
            filename = filename[:idx] + save_content_types[content_type]
        else:
            filename += save_content_types[content_type]

        filepath = os.path.join(folderpath, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        svg = str(response.content)[2:-1]
        if logo_QFMC:
            idx_start = svg.index("<g")

            with open(os.path.join("mysite", "TVs", "QFMC", "sources", "logo_spotify_code.txt"), "r") as file:
                QFMC_logo = file.read()

            svg = svg[:idx_start] + QFMC_logo + "\n</svg>"

        with open(filepath, "w") as file:
            with lock_escritura:
                file.write(svg)

        return filepath


def actualizar_codigos_programados(
        filepath_programacion: str = None,
        limpiar_carpeta: bool = False):

    class CancionDelDia(NamedTuple):
        URI_or_URL: str
        fecha: str | datetime
        color_fondo: str
        color_barras: bool
        ancho: int
        tipo_archivo: str
        logo_QFMC: bool

    path = filepath_programacion if filepath_programacion else os.path.join("mysite", "TVs", "QFMC"
                                                                            "Cancion_del_dia", "programacion.csv")
    canciones: list[CancionDelDia] = []

    with open(path, "r") as file:
        for line in map(lambda x: x.strip(), file.readlines()[1:]):
            canciones.append(CancionDelDia._make(line.split(",")))

    if limpiar_carpeta:
        folderpath = os.path.join(os.path.dirname(path), "spotify_codes")
        if os.path.exists(folderpath):
            for file in os.listdir(folderpath):
                if file.endswith((".svg", ".png", ".bak")) and not file.endswith("default.svg"):
                    os.remove(os.path.join(folderpath, file))

    for cancion in canciones:
        svg_path = guardar_codigo_spotify(
            URI_or_URL=cancion.URI_or_URL,
            fecha=cancion.fecha,
            color_fondo=cancion.color_fondo,
            color_barras=cancion.color_barras == "True",
            ancho=int(cancion.ancho),
            tipo_archivo=cancion.tipo_archivo,
            logo_QFMC=cancion.logo_QFMC == "True"
        )
        add_bar_animations(svg_path)


def actualizar_codigo_del_dia():
    raise NotImplementedError()


def importar_programacion_notion(limpiar_carpeta: bool = True):

    # Solicitar database de Notion
    url = f"https://api.notion.com/v1/databases/{DATABASES_IDS['cancion_del_dia']}/query"
    payload = {'page_size': 100}

    data = []
    run = True
    while run:
        response = requests.post(url, headers=HEADERS_OSCAR_CAI, json=payload)
        data.extend(response.json().get("results", []))
        run = response.json().get("has_more", False)
        if response.json().get("next_cursor", None):
            payload["start_cursor"] = response.json()["next_cursor"]

    if limpiar_carpeta:
        folderpath = os.path.join("mysite", "TVs", "QFMC",
                                  "Cancion_del_dia", "spotify_codes")

        if os.path.exists(folderpath):
            for file in os.listdir(folderpath):
                if file.endswith((".svg", ".png", ".bak")) and not file.endswith("default.svg"):
                    os.remove(os.path.join(folderpath, file))
            printt(f"Carpeta '{folderpath}' limpiada.")
        else:
            printt(f"No se encontró el path {folderpath}")

    # Función para generar y guardar el código en carpeta
    def generar_y_animar(_data_cancion: dict):
        _svg_path = guardar_codigo_spotify(**_data_cancion)
        add_bar_animations(_svg_path)
        printt(f"Spotify Code ANIMADO y GUARDADO ({_svg_path})")

    threads = []
    for entrada in data:
        if not entrada["properties"]["Fecha"]["date"]["start"] or not entrada["properties"]["URL"]["url"]:
            continue

        fecha_standard = entrada["properties"]["Fecha"]["date"]["start"]
        data_cancion = {
            "fecha": f"{fecha_standard[8:10]}_{fecha_standard[5:7]}_{fecha_standard[2:4]}",
            "URI_or_URL": entrada["properties"]["URL"]["url"],
            "nombre_cancion": entrada["properties"]["Nombre"]["title"][0]['plain_text']
        }

        # Parámetros opcionales
        if entrada["properties"]["Color Fondo"]["rich_text"]:
            data_cancion["color_fondo"] = entrada["properties"]["Color Fondo"]["rich_text"][0]["plain_text"]

        if entrada["properties"]["Ancho"]["number"]:
            data_cancion['ancho'] = entrada["properties"]["Ancho"]["number"]

        if entrada["properties"]["Tipo de Archivo"]["select"]:
            data_cancion['tipo_archivo'] = entrada["properties"]["Tipo de Archivo"]["select"]["name"]

        data_cancion["color_barras"] = entrada["properties"]["Barras Blancas"]["checkbox"]
        data_cancion["logo_QFMC"] = entrada["properties"]["Logo QFMC"]["checkbox"]

        printt("Generando Código, Canción:", data_cancion["nombre_cancion"])
        thread = Thread(
            name=f"Thread Canción: {data_cancion['nombre_cancion']}",
            target=generar_y_animar,
            args=(data_cancion,)
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":

    guardar_codigo_spotify(
        "https://open.spotify.com/intl-es/track/4Qs3OEgzBPGPmRR5QJ0UIs?si=5N3g_cZfQoWT3glmiejzNQ&nd=1&dlsi=34e42cbbfeac4655",
        filename="default",
        tipo_archivo=".svg",
        folderpath=os.path.join(
            os.path.dirname(__file__),
            "Cancion_del_dia",
            "spotify_codes"
        )
    )

    importar_programacion_notion()
