"""Normalización de datos de estaciones ITV.

Módulo compartido para todos los extractores con funciones de normalización
de texto, coordenadas, horarios, y otros campos comunes.
"""

import re
from typing import Optional, Tuple
from unidecode import unidecode

# Mapeo de días en gallego, catalán, valenciano al español
DIAS_MAPPING = {
    # Gallego
    'luns': 'lunes',
    'martes': 'martes',
    'mércores': 'miércoles',
    'xoves': 'jueves',
    'venres': 'viernes',
    'sábado': 'sábado',
    'domingo': 'domingo',
    # Catalán / Valenciano
    'dilluns': 'lunes',
    'dimarts': 'martes',
    'dimecres': 'miércoles',
    'dijous': 'jueves',
    'divendres': 'viernes',
    'dissabte': 'sábado',
    'diumenge': 'domingo',
    # Inglés
    'monday': 'lunes',
    'tuesday': 'martes',
    'wednesday': 'miércoles',
    'thursday': 'jueves',
    'friday': 'viernes',
    'saturday': 'sábado',
    'sunday': 'domingo',
    'mon': 'lunes',
    'tue': 'martes',
    'wed': 'miércoles',
    'thu': 'jueves',
    'fri': 'viernes',
    'sat': 'sábado',
    'sun': 'domingo',
}

# Abreviaturas y patrones especiales
DIAS_ESPECIALES_MAPPING = {
    'fds': 'fines de semana',
    'fin de semana': 'fines de semana',
    'festivos': 'festivos',
    'vacaciones': 'vacaciones',
    'excepto': 'excepto',
    'laborales': 'días laborales',
    'laborables': 'días laborales',
}


def normalize_text(s: str) -> str:
    """Normaliza un texto: unidecode, strip, lowercase, espacios a guiones bajos.
    
    Útil para hacer matching flexible de nombres de columnas y construir códigos internos.
    """
    if not s:
        return ""
    return unidecode(str(s)).strip().lower().replace(' ', '_')


def normalize_estacion_name(nombre: Optional[str]) -> Optional[str]:
    """Normaliza nombre de estación: añade prefijo si no existe y convierte variantes gallegas."""
    if nombre is None:
        return None
    
    nombre = str(nombre).strip()
    
    # Convertir variantes gallegas a castellano
    nombre = re.sub(r'\bEstación\s+ITV\s+da\b', 'Estación ITV de', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\bEstación\s+ITV\s+do\b', 'Estación ITV de', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\bEstación\s+ITV\s+dos\b', 'Estación ITV de', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'\bEstación\s+ITV\s+das\b', 'Estación ITV de', nombre, flags=re.IGNORECASE)
    
    if not re.match(r'^\s*Estación\s+ITV', nombre, flags=re.IGNORECASE):
        nombre = f"Estación ITV de {nombre}"
    
    return nombre


def translate_day(day_str: str) -> str:
    """Traduce un nombre de día a castellano."""
    if not day_str:
        return day_str
    
    day_lower = unidecode(day_str.strip().lower())
    return DIAS_MAPPING.get(day_lower, day_str.lower())


def parse_schedule_line(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parsea línea de horario para extraer hora_apertura, hora_cierre, días."""
    if not line:
        return None, None, None
    
    line = line.strip()
    # busca hh:mm o hh.mm
    hora_pattern = r'(\d{1,2})[:.](\d{2})'
    matches = re.findall(hora_pattern, line)
    if len(matches) < 2:
        return None, None, None
    
    # matches[0] contiene la primera hora encontrada (apertura). matches[0][0] es la hora, matches[0][1] son los minutos.
    try:
        h_open = f"{int(matches[0][0]):02d}:{matches[0][1]}"
        h_close = f"{int(matches[1][0]):02d}:{matches[1][1]}"
    except (ValueError, IndexError):
        return None, None, None
    
    dias_match = re.search(r'\(([^)]+)\)', line)
    dias_str = dias_match.group(1).strip() if dias_match else None
    
    return h_open, h_close, dias_str


def normalize_days_string(dias_raw: Optional[str]) -> Optional[str]:
    """Normaliza cadena de días a formato estándar."""      
    if not dias_raw:
        return None
    
    dias_raw = dias_raw.strip().lower()
    dias_raw = unidecode(dias_raw)
    
    for old, new in DIAS_MAPPING.items():
        dias_raw = re.sub(r'\b' + old + r'\b', new, dias_raw)
    
    if '-' in dias_raw or ' a ' in dias_raw:
        match = re.search(r'(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s*[-a]\s*(lunes|martes|miercoles|jueves|viernes|sabado|domingo)', dias_raw)
        if match:
            day1 = match.group(1).replace('miercoles', 'miércoles')
            day2 = match.group(2).replace('miercoles', 'miércoles')
            dias_raw = f"de {day1} a {day2}"
    
    dias_raw = re.sub(r',\s*', ' y ', dias_raw)
    
    if not dias_raw.startswith('de'):
        dias_raw = f"de {dias_raw}"
    
    return dias_raw


def normalize_schedule(horario_raw: Optional[str]) -> Optional[str]:
    """Normaliza horario a: 'de HH:MM a HH:MM horas (de DÍAS)'."""
    if not horario_raw:
        return None
    
    horario_raw = str(horario_raw).strip()
    horario_raw = re.sub(r'\s+e\s+(?=de\s*\d)', ' y ', horario_raw, flags=re.IGNORECASE)
    
    partes_normalizadas = []
    patron_rango = r'de\s+(\d{1,2}[.:](\d{2}))\s+a\s+(\d{1,2}[.:](\d{2}))(?:\s+.*?horas)?(?:\s+\(([^)]*)\))?'
    matches = re.finditer(patron_rango, horario_raw, flags=re.IGNORECASE)
    rangos_encontrados = list(matches)
    
    if not rangos_encontrados:
        h_open, h_close, dias_raw = parse_schedule_line(horario_raw)
        if h_open and h_close:
            parte = f"de {h_open} a {h_close} horas"
            if dias_raw:
                dias_norm = normalize_days_string(dias_raw)
                if dias_norm:
                    parte += f" ({dias_norm})"
            return parte
        return None
    
    for i, match in enumerate(rangos_encontrados):
        h_open_str = match.group(1)
        h_close_str = match.group(3)
        dias_raw = match.group(5)
        
        h_open = h_open_str.replace('.', ':')
        h_close = h_close_str.replace('.', ':')
        
        h_open_parts = h_open.split(':')
        h_close_parts = h_close.split(':')
        h_open = f"{int(h_open_parts[0]):02d}:{h_open_parts[1]}"
        h_close = f"{int(h_close_parts[0]):02d}:{h_close_parts[1]}"
        
        parte = f"de {h_open} a {h_close} horas"
        
        if dias_raw:
            dias_norm = normalize_days_string(dias_raw)
            if dias_norm:
                parte += f" ({dias_norm})"
        
        partes_normalizadas.append(parte)
    
    return " y ".join(partes_normalizadas) if partes_normalizadas else None


def capitalize_provincia(nombre: str) -> str:
    """Normaliza el nombre de la provincia al formato oficial.
    
    Usa la función normalizar_provincia de spanish_locations para manejar
    correctamente casos especiales como "A Coruña", "La Coruña" -> "A Coruña".
    """
    if not nombre:
        return nombre
    
    from .spanish_locations import normalizar_provincia
    return normalizar_provincia(nombre)


def normalize_tipo_estacion(tipo_raw: Optional[str]) -> str:
    """Normaliza el tipo de estación a uno de los valores estándar."""
    if not tipo_raw:
        return 'estacion_fija'  # default
    
    tipo_lower = str(tipo_raw).lower()
    
    if 'móvil' in tipo_lower or 'movil' in tipo_lower:
        return 'estacion_movil'
    elif 'fija' in tipo_lower or 'fijo' in tipo_lower:
        return 'estacion_fija'
    elif 'agrícola' in tipo_lower or 'agricola' in tipo_lower:
        return 'otros'
    else:
        # Si no se reconoce, devolver 'estacion_fija' como default seguro
        return 'estacion_fija'


def normalize_codigo_postal(cp_raw) -> Optional[str]:
    """Normaliza código postal a string de exactamente 5 dígitos. 
    Valida que esté en el rango válido de España (01000-52999).
    Retorna None si no es válido."""
    if not cp_raw:
        return None
    
    try:
        cp_int = int(cp_raw)
        cp_str = str(cp_int)
    except (ValueError, TypeError):
        try:
            cp_str = str(cp_raw).strip()
        except:
            return None
    
    # Eliminar caracteres no numéricos
    cp_str = re.sub(r'\D', '', cp_str)
    
    # Verificar que tenga entre 1 y 5 dígitos
    if not (cp_str.isdigit() and 1 <= len(cp_str) <= 5):
        return None
    
    # Normalizar a 5 dígitos con ceros a la izquierda
    cp_normalizado = cp_str.zfill(5)
    cp_int = int(cp_normalizado)
    
    # Validar rango de códigos postales de España (01000-52999)
    if not (1000 <= cp_int <= 52999):
        return None
    
    return cp_normalizado


def is_valid_email(email_str: str) -> bool:
    """Verifica si el string es un email válido (no una URL)."""
    if not email_str:
        return False
    
    email_str = str(email_str).strip().lower()
    
    if email_str.startswith('www.') or email_str.startswith('http'):
        return False
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email_str))


def separate_email_and_url(value: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Separa email y URL de un valor que puede contener cualquiera de los dos.
    Retorna (email, url).
    """
    if not value:
        return None, None
    
    value_str = str(value).strip()
    
    if is_valid_email(value_str):
        return value_str, None
    
    if 'www.' in value_str or value_str.startswith('http'):
        if not value_str.startswith('http'):
            value_str = f"http://{value_str}"
        return None, value_str
    
    return None, None


def normalize_direccion(direccion: Optional[str]) -> Optional[str]:
    """Normaliza una dirección, removiendo prefijos de tipo estación."""
    if direccion is None:
        return None
    
    direccion = str(direccion).strip()
    
    direccion = re.sub(r'^I\.?T\.?V\.?\s+(Móvil|Movil|Fija|Fijo)\s+', '', direccion, flags=re.IGNORECASE)
    direccion = re.sub(r'\s+', ' ', direccion).strip()
    
    return direccion


def parse_single_coordinate(part: str) -> Optional[float]:
    """Parsea una parte de coordenada (lat o lon) en distintos formatos.

    Soporta:
    - Decimal: '42.906076' o '-8.498523'
    - DDM: "43° 18.856'" o "43° 18.856'" (grados + minutos.decimales)
    - Microgrados: '413028' → '41302800' → 41.302800° (formato entero de 6-8 dígitos)
    - Con sufijos N/S/E/W/O (detecta signo automáticamente)
    
    Returns:
        float o None si no se pudo parsear.
    """
    if not part:
        return None
    s = unidecode(str(part)).strip()

    # Decimal degrees simple: "42.906076" or "-8.498523"
    m = re.match(r'^\s*([-+]?\d+\.\d+)\s*$', s)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None

    # Microgrados: formato entero sin punto decimal de 6-8 dígitos
    # Ejemplo: 413028 → 41302800 → 41.302800 grados
    m = re.match(r'^\s*([-+])?(\d{6,8})\s*$', s)
    if m:
        try:
            sign = m.group(1)
            digits = m.group(2)
            # Completar con ceros a la derecha hasta tener 8 dígitos
            digits_padded = digits.ljust(8, '0')
            # Convertir de microgrados a grados (dividir por 1000000)
            coord = int(digits_padded) / 1000000.0
            if sign == '-':
                coord = -coord
            return coord
        except Exception:
            pass

    # DDM: degrees and decimal minutes, e.g. "43 18.856" or "43° 18.856'"
    m = re.search(r"([-+]?\d+)\D+(\d+\.\d+)", s)
    if m:
        try:
            degrees = float(m.group(1))
            minutes = float(m.group(2))
            dd = abs(degrees) + minutes / 60.0
            # Determine sign: negative if text contains '-' or W/Oeste
            if '-' in s or 'W' in s.upper() or 'O' in s.upper():
                dd = -dd
            return -dd if degrees < 0 and not ('-' in s) else dd
        except Exception:
            return None

    # Fallback: try to extract any two numbers
    nums = re.findall(r'[-+]?\d+\.\d+|[-+]?\d+', s)
    if nums:
        try:
            return float(nums[0])
        except Exception:
            return None

    return None


def parse_coordinates(coord_str: str) -> Tuple[Optional[float], Optional[float]]:
    """Convierte string de coordenadas a (lat, lon) flotantes.

    Acepta varios formatos:
    - "42.906076, -8.498523"
    - "43° 18.856', 8° 29.911'" (DDM)
    - Mezcla de formatos

    Returns:
        Tuple (lat, lon) o (None, None) si no pudo parsear.
    """
    if coord_str is None:
        return None, None
    try:
        s = str(coord_str)
        parts = [p.strip() for p in s.split(',') if p.strip()]
        lat = parse_single_coordinate(parts[0]) if len(parts) > 0 else None
        lon = parse_single_coordinate(parts[1]) if len(parts) > 1 else None
        return lat, lon
    except Exception:
        return None, None


def find_column(raw_item: dict, *variants: str) -> Optional[str]:
    """Busca una columna en un raw item por múltiples variantes de nombres.

    Normaliza los nombres de columnas y los variantes para hacer matching flexible.
    Útil cuando los CSVs de distintas fuentes tienen nombres de columnas diferentes.

    Args:
        raw_item: dict con los datos crudos (del CSV).
        *variants: strings con posibles nombres de la columna (en cualquier formato).

    Returns:
        Nombre de la columna encontrada en raw_item, o None si no hay coincidencia.

    Example:
        col_nombre = find_column(raw_item, 'nome_da_estacion', 'nombre', 'nombre_estacion')
    """
    norm_map = {normalize_text(k): k for k in raw_item.keys()}
    for v in variants:
        nv = normalize_text(v)
        if nv in norm_map:
            return norm_map[nv]
    return None


def make_code(prefix: str, text: Optional[str]) -> Optional[str]:
    """Construye un código interno: prefix-normalized_text.
    
    Args:
        prefix: prefijo del código (ej: "GAL-PROV", "CAT-LOC").
        text: texto a normalizar.

    Returns:
        String "prefix-normalized_text" o None si text es None.
    """
    if text is None:
        return None
    return f"{prefix}-{normalize_text(text)}"


def safe_get(d: dict, key: Optional[str]) -> Optional[str]:
    """Obtiene un valor del dict de forma segura cuando la key puede ser None.
    
    Args:
        d: diccionario.
        key: clave a buscar (puede ser None si no se encontró la columna).

    Returns:
        Valor en d[key] o None si key es None o no existe.
    """
    if key is None:
        return None
    return d.get(key)
