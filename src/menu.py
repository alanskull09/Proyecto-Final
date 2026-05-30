import os
from src.sbac.core import SBAC

def mostrar_menu():
    print("\n" + "="*45)
    print("📦 SBAC - Menú Principal Interactivo")
    print("="*45)
    print("1. Inicializar repositorio (init)")
    print("2. Añadir archivo al seguimiento (add)")
    print("3. Ver estado del repositorio (status)")
    print("4. Crear una nueva versión (commit)")
    print("5. Ver el historial de versiones (history)")
    print("6. Marcar una línea base (baseline)")
    print("7. Mostrar diferencias (diff)")
    print("8. Regresar a versión anterior (checkout)")
    print("9. Salir")
    print("="*45)

def ejecutar():
    app = SBAC()
    while True:
        mostrar_menu()
        opcion = input("\nElige una opción (1-9): ")

        try:
            if opcion == "1":
                print(app.init())
            elif opcion == "2":
                archivo = input("Ruta del archivo: ")
                print(app.add(archivo))
            elif opcion == "3":
                archivos = app.status()
                print("Archivos en seguimiento:\n" + "\n".join([f"  - {f}" for f in archivos]) if archivos else "Ninguno.")
            elif opcion == "4":
                msg = input("Mensaje del commit: ")
                print(app.commit(msg))
            elif opcion == "5":
                for c in app.history():
                    print(f"[{c['id']}] {c['timestamp']} - {c['message']}")
            elif opcion == "6":
                nombre = input("Nombre para la línea base: ")
                print(app.baseline(nombre))
            elif opcion == "7":
                v1 = input("Versión 1 (ID o Línea Base): ")
                v2 = input("Versión 2 (ID o Línea Base): ")
                for f, d in app.diff(v1, v2):
                    print(f"\n--- Diferencias en {f} ---")
                    for linea in d: print(linea, end="")
            elif opcion == "8":
                v = input("Versión a restaurar (ID o Línea Base): ")
                print(app.checkout(v))
            elif opcion == "9":
                break
            else:
                print("Opción inválida.")
        except Exception as e:
            print(f"⚠️ Error: {str(e)}")

if __name__ == "__main__":
    ejecutar()