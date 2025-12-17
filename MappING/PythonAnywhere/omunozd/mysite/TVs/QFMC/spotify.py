import requests, traceback
from datetime import datetime
from typing import NamedTuple
import os

from mysite.TVs.QFMC.Cancion_del_dia.add_svg_bar_anim import add_bar_animations

def guardar_codigo_spotify(
        URI_or_URL: str, 
        fecha: datetime | str | None = None,
        color_fondo: str = "fff8e8",
        color_barras: bool = False,
        ancho: int = 1000,
        tipo_archivo: str = ".svg",
        logo_QFMC: bool = True,
        folderpath: str = None,
        filename: str = None):
    
    folderpath = os.path.join("mysite","TVs","QFMC",
        "Cancion_del_dia","spotify_codes") if not folderpath else folderpath
    
    if "http" in URI_or_URL:
        URL_data = URI_or_URL.split("/")
        URI = f"spotify:{URL_data[4]}:{URL_data[5].split("?")[0]}"
    elif "spotify:" in URI_or_URL:
        URI = URI_or_URL
    else:
        raise ValueError(f"URI o URL no reconocida: {URI_or_URL}")
    
    save_content_types = {
        "image/svg+xml": ".svg",
        "image/png": ".png"
    }

    if tipo_archivo not in save_content_types.values():
        raise ValueError(f"Tipo de archivo {tipo_archivo} no válido. Se aceptan: {" , ".join(save_content_types.values())}")
    
    url_base = "https://scannables.scdn.co/uri/plain/"
    parametros_url = [tipo_archivo[1:],
                      color_fondo,
                      "white" if color_barras else "black",
                      str(ancho),
                      URI]
    url = url_base + "/".join(parametros_url)

    try:
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Error ({response.status_code}) en la solicitud.\nGET: {url}")
        
    except:
        traceback.print_exc()
        print("\nError al solicitar generación de código.")
        raise ConnectionError("Error HTTP: No se pudo realizar la solicitud.")
    
    else:
        if isinstance(fecha, datetime):
            str_fecha = fecha.strftime("%d_%m_%y")
        elif type(fecha) == str:
            str_fecha = fecha
        else:
            str_fecha = datetime.today().strftime("%d_%m_%y")

        content_type = response.headers.get("content-type")

        if not filename:
            filename = "QFMC_cancionDelDia_" + str_fecha + save_content_types[content_type]
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

            with open(os.path.join("mysite","TVs","QFMC","sources","logo_spotify_code.txt"),"r") as file:
                QFMC_logo = file.read()
            
            svg = svg[:idx_start] + QFMC_logo + "\n</svg>"

        with open(filepath, "w") as file:
            file.write(svg)

        print(f"Código Spotify guardado en '{filepath}'")
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

    path = filepath_programacion if filepath_programacion else os.path.join("mysite","TV","QFMC"
        "Cancion_del_dia","programacion.csv")
    canciones: list[CancionDelDia] = []

    with open(path,"r") as file:
        for line in map(lambda x: x.strip(), file.readlines()[1:]):
            canciones.append(CancionDelDia._make(line.split(",")))
    
    if limpiar_carpeta:
        folderpath = os.path.join(os.path.dirname(path),"spotify_codes")
        if os.path.exists(folderpath):
            for file in os.listdir(folderpath):
                if file.endswith((".svg", ".png", ".bak")) and not file.endswith("default.svg"):
                    os.remove(os.path.join(folderpath, file))

    for cancion in canciones:
        svg_path = guardar_codigo_spotify(
            URI_or_URL= cancion.URI_or_URL,
            fecha= cancion.fecha,
            color_fondo= cancion.color_fondo,
            color_barras= cancion.color_barras == "True",
            ancho= int(cancion.ancho),
            tipo_archivo= cancion.tipo_archivo,
            logo_QFMC= cancion.logo_QFMC == "True"
        )
        add_bar_animations(svg_path)

def actualizar_codigo_del_dia():
    raise NotImplementedError()

def importar_programacion_notion():
    raise NotImplementedError()

if __name__ == "__main__":

    guardar_codigo_spotify(
        "https://open.spotify.com/intl-es/track/4Qs3OEgzBPGPmRR5QJ0UIs?si=5N3g_cZfQoWT3glmiejzNQ&nd=1&dlsi=34e42cbbfeac4655",
        filename="default",
        tipo_archivo=".svg",
        folderpath= os.path.join(
            os.path.dirname(__file__),
            "Cancion_del_dia",
            "spotify_codes"
        )
    )

    actualizar_codigos_programados(limpiar_carpeta=True)