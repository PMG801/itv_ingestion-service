#!/usr/bin/env python3
"""
Script para levantar todos los servicios ITV
"""
import os
import sys
import signal
import subprocess
import time
from pathlib import Path
import shutil
import platform
from threading import Thread
import asyncio

# Detectar sistema operativo
IS_WINDOWS = platform.system() == 'Windows'


class ServiceManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.resolve()
        self.logs_dir = self.base_dir / "logs"
        self.processes = {}
        self.tail_process = None
        
        # Crear directorio de logs
        self.logs_dir.mkdir(exist_ok=True)
        
        # Configurar manejo de señales
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
    
    def cleanup(self, signum=None, frame=None):
        """Función para limpiar procesos al salir"""
        print()
        print("🛑 Deteniendo servicios...")
        
        # Detener proceso de tail
        if self.tail_process:
            self.tail_process.terminate()
            try:
                self.tail_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.tail_process.kill()
        
        # Detener todos los servicios
        for name, process in self.processes.items():
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        print("✅ Todos los servicios detenidos")
        print()
        print("Logs guardados en:")
        print(f"  - {self.logs_dir}/api_carga.log")
        print(f"  - {self.logs_dir}/api_busqueda.log")
        print(f"  - {self.logs_dir}/valencia.log")
        print(f"  - {self.logs_dir}/catalunya.log")
        print(f"  - {self.logs_dir}/galicia.log")
        sys.exit(0)
    
    def copy_data_files(self):
        """Verificar que existen los archivos de datos"""
        data_dir = self.base_dir / "extractor_services" / "data"
        
        # Verificar que el directorio de datos existe
        if not data_dir.exists():
            print("⚠️  Directorio de datos no existe, creándolo...")
            data_dir.mkdir(parents=True, exist_ok=True)
        
        # Verificar archivos requeridos
        required_files = ["estaciones_cv.json", "estaciones_cat.xml", "estaciones_gal.csv"]
        missing_files = [f for f in required_files if not (data_dir / f).exists()]
        
        if missing_files:
            print(f"⚠️  Archivos de datos faltantes: {', '.join(missing_files)}")
            print(f"   Por favor, coloca los archivos en: {data_dir}")
        else:
            print("✅ Archivos de datos encontrados")
    
    def activate_venv(self):
        """Verificar si existe entorno virtual"""
        if IS_WINDOWS:
            venv_path = self.base_dir / "venv" / "Scripts" / "activate.bat"
        else:
            venv_path = self.base_dir / "venv" / "bin" / "activate"
        
        if venv_path.exists():
            print("✅ Entorno virtual detectado")
            return True
        else:
            print(f"⚠️  No se encontró entorno virtual en {self.base_dir}/venv")
            return False
    
    def clear_logs(self):
        """Limpiar logs anteriores"""
        log_files = ["api_carga.log", "api_busqueda.log", "valencia.log", "catalunya.log", "galicia.log"]
        for log_file in log_files:
            (self.logs_dir / log_file).write_text("")
    
    def _create_windows_wrapper(self, module, port, cwd):
        """Crear script wrapper para configurar SelectorEventLoop en Windows"""
        wrapper_content = f'''#!/usr/bin/env python3
import asyncio
import sys
import platform

# Configurar SelectorEventLoop en Windows para psycopg
if platform.system() == 'Windows':
    # Suprimir DeprecationWarning de Python 3.14+
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning, message='.*WindowsSelectorEventLoopPolicy.*')
    warnings.filterwarnings('ignore', category=DeprecationWarning, message='.*set_event_loop_policy.*')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Importar y ejecutar uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run("{module}", host="0.0.0.0", port={port})
'''
        wrapper_path = Path(cwd) / f"_uvicorn_wrapper_{port}.py"
        wrapper_path.write_text(wrapper_content)
        return str(wrapper_path)
    
    def start_service(self, name, port, cwd, pythonpath=None, delay=0, needs_selector_loop=False):
        """Iniciar un servicio con uvicorn"""
        print(f"▶ {name} (puerto {port})")
        
        log_file_name = name.lower().replace(" ", "_").replace("extractor_", "") + ".log"
        if name == "API Carga":
            log_file_name = "api_carga.log"
        elif name == "API Búsqueda":
            log_file_name = "api_busqueda.log"
        
        log_file = self.logs_dir / log_file_name
        
        # Determinar el módulo a ejecutar
        if name == "API Carga":
            module = "app.carga.main:app"
        elif name == "API Búsqueda":
            module = "app.busqueda.main:app"
        else:
            module = "main:app"
        
        env = os.environ.copy()
        if pythonpath:
            env['PYTHONPATH'] = pythonpath
        
        # En Windows, configurar el event loop policy para servicios con async DB
        if IS_WINDOWS and needs_selector_loop:
            env['UVICORN_LOOP'] = 'asyncio'
            # Crear un script wrapper para configurar el event loop antes de uvicorn
            wrapper_script = self._create_windows_wrapper(module, port, cwd)
            python_exe = sys.executable
            uvicorn_cmd = [python_exe, wrapper_script]
        else:
            # Usar el intérprete de Python actual
            python_exe = sys.executable
            uvicorn_cmd = [python_exe, "-m", "uvicorn", module, "--port", str(port)]
        
        with open(log_file, 'a') as log:
            process = subprocess.Popen(
                uvicorn_cmd,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=log
            )
        
        self.processes[name] = process
        
        if delay > 0:
            time.sleep(delay)
    
    def start_all_services(self):
        """Iniciar todos los servicios"""
        print("🚀 Iniciando servicios ITV Buscador...")
        print()
        
        # Verificar y copiar archivos de datos
        self.copy_data_files()
        
        # Activar entorno virtual
        self.activate_venv()
        
        print()
        print("Iniciando servicios...")
        print()
        
        # Limpiar logs
        self.clear_logs()
        
        # API de Carga (puerto 8000)
        self.start_service(
            name="API Carga",
            port=8000,
            cwd=str(self.base_dir),
            needs_selector_loop=False,
            delay=2
        )
        
        # API de Búsqueda (puerto 8004)
        self.start_service(
            name="API Búsqueda",
            port=8004,
            cwd=str(self.base_dir),
            needs_selector_loop=False,
            delay=1
        )
        
        # Extractor Valencia (puerto 8001)
        self.start_service(
            name="Extractor Valencia",
            port=8001,
            cwd=str(self.base_dir / "extractor_services" / "valencia_api"),
            pythonpath=str(self.base_dir / "extractor_services"),
            delay=1
        )
        
        # Extractor Catalunya (puerto 8002)
        self.start_service(
            name="Extractor Catalunya",
            port=8002,
            cwd=str(self.base_dir / "extractor_services" / "catalunya_api"),
            pythonpath=str(self.base_dir / "extractor_services"),
            delay=1
        )
        
        # Extractor Galicia (puerto 8003)
        self.start_service(
            name="Extractor Galicia",
            port=8003,
            cwd=str(self.base_dir / "extractor_services" / "galicia_api"),
            pythonpath=str(self.base_dir / "extractor_services"),
            delay=2
        )
        
        self.print_info()
        
        # Mostrar logs en tiempo real
        self.show_logs()
    
    def print_info(self):
        """Imprimir información de los servicios"""
        print()
        print("=" * 50)
        print("✅ Todos los servicios iniciados")
        print("=" * 50)
        print()
        print("Endpoints disponibles:")
        print("  - API de Carga:        http://localhost:8000/docs")
        print("  - API de Búsqueda:     http://localhost:8004/docs")
        print("  - Extractor Valencia:  http://localhost:8001/docs")
        print("  - Extractor Catalunya: http://localhost:8002/docs")
        print("  - Extractor Galicia:   http://localhost:8003/docs")
        print()
        print("Logs guardados en:")
        print("  - logs/api_carga.log")
        print("  - logs/api_busqueda.log")
        print("  - logs/valencia.log")
        print("  - logs/catalunya.log")
        print("  - logs/galicia.log")
        print()
        print("Para ver los logs en tiempo real:")
        print("  tail -f logs/api_carga.log")
        print("  tail -f logs/api_busqueda.log")
        print("  tail -f logs/valencia.log")
        print("  tail -f logs/catalunya.log")
        print("  tail -f logs/galicia.log")
        print()
        print("  # O todos a la vez:")
        print("  tail -f logs/*.log")
        print()
        print("Para ejecutar extracciones (desde API de Carga):")
        print("  curl -X POST http://localhost:8000/api/carga/ -d '{\"fuente\": \"VAL\"}'")
        print("  curl -X POST http://localhost:8000/api/carga/ -d '{\"fuente\": \"CAT\"}'")
        print("  curl -X POST http://localhost:8000/api/carga/ -d '{\"fuente\": \"GAL\"}'")
        print()
        print("Para buscar estaciones (desde API de Búsqueda):")
        print("  curl http://localhost:8004/api/estaciones/")
        print("  curl http://localhost:8004/api/provincias/")
        print()
        print("Presiona Ctrl+C para detener todos los servicios")
        print()
    
    def tail_logs_thread(self, log_files):
        """Función para leer logs en tiempo real (alternativa multiplataforma a tail -f)"""
        # Abrir todos los archivos
        file_handles = []
        for log_file in log_files:
            try:
                f = open(log_file, 'r')
                # Ir al final del archivo
                f.seek(0, 2)
                file_handles.append((log_file.name, f))
            except Exception:
                pass
        
        try:
            while True:
                for name, f in file_handles:
                    line = f.readline()
                    if line:
                        print(f"[{name}] {line}", end='')
                time.sleep(0.1)
        except Exception:
            pass
        finally:
            for _, f in file_handles:
                f.close()
    
    def show_logs(self):
        """Mostrar logs combinados en tiempo real"""
        log_files = list(self.logs_dir.glob("*.log"))
        
        if IS_WINDOWS:
            # En Windows, usar implementación Python
            print("Mostrando logs en tiempo real...")
            if log_files:
                tail_thread = Thread(target=self.tail_logs_thread, args=(log_files,), daemon=True)
                tail_thread.start()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
        else:
            # En Linux/Mac, usar tail -f si está disponible
            if log_files:
                try:
                    self.tail_process = subprocess.Popen(
                        ["tail", "-f"] + [str(f) for f in log_files],
                        stdout=sys.stdout,
                        stderr=sys.stderr
                    )
                    self.tail_process.wait()
                except FileNotFoundError:
                    # Si tail no está disponible, usar implementación Python
                    print("tail no disponible, usando implementación alternativa...")
                    tail_thread = Thread(target=self.tail_logs_thread, args=(log_files,), daemon=True)
                    tail_thread.start()
                    try:
                        while True:
                            time.sleep(1)
                    except KeyboardInterrupt:
                        pass
            else:
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass


def main():
    manager = ServiceManager()
    manager.start_all_services()


if __name__ == "__main__":
    main()
