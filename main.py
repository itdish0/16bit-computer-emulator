
from source.compiler import Compiler
from source.computer import Computer
import pygame


def run_file(file_name='snake_os'):
    compiler.compile_full(f"{file_name}.txt", "Computer\\System\\test.os")
    computer.boot()
    computer.run()

def main():
    try:
        print("Pick an assembly file to run!")
        print("Or just hit enter to play snake \x01")
        file_name = input(">>")
        try:
            if file_name == '':
                run_file()
            else:
                run_file(file_name)
        except FileNotFoundError as e:
            print("Oh dear, it looks like we don't have the file you wanted...")
            print(f"Here's the error: {e}")
        except ValueError as e:
            print("Oh dear, it looks like the compiler had an error...")
            print(f"Here's the error: {e}")
    finally:
        pygame.quit()  # Just in case...


computer = Computer()
compiler = Compiler()
main()
