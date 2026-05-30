#!/usr/bin/env python3
import argparse
import sys
from sbac.core import SBAC

def main():
    parser = argparse.ArgumentParser(description="Sistema Básico de Administración de Configuración (SBAC)")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    subparsers.add_parser("init", help="Inicializar un repositorio")
    
    parser_add = subparsers.add_parser("add", help="Añadir archivos al seguimiento")
    parser_add.add_argument("archivo", type=str, help="Ruta del archivo a añadir")
    
    subparsers.add_parser("status", help="Mostrar estado del repositorio")
    
    parser_commit = subparsers.add_parser("commit", help="Crear una nueva versión")
    parser_commit.add_argument("mensaje", type=str, help="Mensaje del commit")
    
    subparsers.add_parser("history", help="Listar historial de versiones")
    
    parser_baseline = subparsers.add_parser("baseline", help="Marcar una versión como línea base")
    parser_baseline.add_argument("nombre", type=str, help="Nombre de la línea base")
    parser_baseline.add_argument("--commit", type=str, help="ID del commit (opcional)", default=None)
    
    subparsers.add_parser("list-baselines", help="Listar líneas base disponibles")
    
    parser_diff = subparsers.add_parser("diff", help="Mostrar diferencias entre versiones")
    parser_diff.add_argument("v1", type=str, help="Versión 1")
    parser_diff.add_argument("v2", type=str, nargs='?', default=None, help="Versión 2 (Opcional)")
    
    parser_checkout = subparsers.add_parser("checkout", help="Regresar a una versión anterior")
    parser_checkout.add_argument("version", type=str, help="Versión o línea base")

    args = parser.parse_args()
    app = SBAC()

    try:
        if args.command == "init":
            print(app.init())
        elif args.command == "add":
            print(app.add(args.archivo))
        elif args.command == "status":
            st = app.status()
            print("Estado del repositorio:")
            if st["staged"]:
                print("\nCambios listos para commit (Staged):")
                for f in st["staged"]: print(f"  🟢 {f}")
            if st["modified"]:
                print("\nArchivos modificados (no staged):")
                for f in st["modified"]: print(f"  🟡 {f}")
            if st["untracked"]:
                print("\nArchivos no rastreados:")
                for f in st["untracked"]: print(f"  ⚪ {f}")
            if not any(st.values()):
                print("\nNada para confirmar, el árbol de trabajo está limpio.")
        elif args.command == "commit":
            print(app.commit(args.mensaje))
        elif args.command == "history":
            for c in app.history():
                print(f"Commit: {c['id']}\nFecha: {c['timestamp']}\nMensaje: {c['message']}\n")
        elif args.command == "baseline":
            print(app.baseline(args.nombre, args.commit))
        elif args.command == "list-baselines":
            for name, cid in app.list_baselines().items():
                print(f"{name} -> {cid}")
        elif args.command == "diff":
            diffs = app.diff(args.v1, args.v2)
            if not diffs:
                print("No hay diferencias detectadas.")
            else:
                for f, d in diffs:
                    print(f"--- Diferencias en {f} ---")
                    sys.stdout.writelines(d)
                    print()
        elif args.command == "checkout":
            print(app.checkout(args.version))
        else:
            parser.print_help()
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()