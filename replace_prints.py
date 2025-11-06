"""
Script para reemplazar print() por logging en archivos Python
Uso: python replace_prints.py
"""
import re
from pathlib import Path


def add_logger_import(content: str, file_path: str) -> str:
    """Agrega import de logger si no existe"""
    module_name = Path(file_path).stem

    if "from app.infrastructure.config.console_logger import ConsoleLogger" not in content:
        lines = content.split('\n')
        import_index = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_index = i + 1

        lines.insert(import_index, "from app.infrastructure.config.console_logger import ConsoleLogger as log")
        content = '\n'.join(lines)

    if f'logger = logging.getLogger(' not in content and 'import logging' in content:
        content = content.replace(
            'import logging',
            f'import logging\n\nlogger = logging.getLogger("trading_simulation.{module_name}")'
        )

    return content


def replace_prints(content: str) -> str:
    """Reemplaza prints por logger calls"""
    lines = content.split('\n')
    new_lines = []

    for line in lines:
        original_line = line
        stripped = line.lstrip()
        indent = line[:len(line) - len(stripped)]

        if stripped.startswith('print('):
            print_match = re.match(r'print\((.*)\)', stripped)
            if print_match:
                args = print_match.group(1)

                if '="*80' in args or "='*80" in args or 'f"{"=' in args or "f'{" in args:
                    new_lines.append(f'{indent}log.separator("=", 80)')
                elif args.startswith('"\\n"') or args.startswith("'\\n'"):
                    continue
                elif '[SIMULACION' in args or '[SIMULATION' in args or '[INICIO' in args:
                    message = args.strip('f"').strip("f'").strip('"').strip("'")
                    new_lines.append(f'{indent}log.success({args}, context="[SIMULATION]")')
                elif '[REBALANCE' in args:
                    new_lines.append(f'{indent}logger.info({args})')
                elif '[DEBUG]' in args or 'DEBUG' in args:
                    message = args.replace('[DEBUG]', '').strip()
                    new_lines.append(f'{indent}logger.debug({message})')
                elif '[ERROR]' in args or 'Error' in args:
                    new_lines.append(f'{indent}logger.error({args})')
                elif '[WARNING]' in args or 'ATENCIÓN' in args:
                    new_lines.append(f'{indent}logger.warning({args})')
                else:
                    new_lines.append(f'{indent}logger.info({args})')
            else:
                new_lines.append(original_line)
        else:
            new_lines.append(original_line)

    return '\n'.join(new_lines)


def process_file(file_path: Path) -> None:
    """Procesa un archivo reemplazando prints"""
    print(f"Procesando: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'print(' not in content:
        print(f"  OK Sin prints, saltando")
        return

    original_content = content
    content = add_logger_import(content, str(file_path))
    content = replace_prints(content)

    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  OK Actualizado")
    else:
        print(f"  - Sin cambios")


def main():
    """Procesa todos los archivos especificados"""
    base_path = Path(__file__).parent

    files_to_process = [
        base_path / "app" / "application" / "services" / "client_accounts_service.py",
        base_path / "app" / "application" / "services" / "daily_orchestrator_service.py",
        base_path / "app" / "application" / "services" / "client_accounts_simulation_service.py",
    ]

    print("="*80)
    print("REEMPLAZANDO PRINT() POR LOGGING")
    print("="*80)

    for file_path in files_to_process:
        if file_path.exists():
            process_file(file_path)
        else:
            print(f"ERROR No encontrado: {file_path}")

    print("\n" + "="*80)
    print("OK PROCESO COMPLETADO")
    print("="*80)


if __name__ == "__main__":
    main()
