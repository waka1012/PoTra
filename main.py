import tkinter as tk
from app import PoTraApp
from formatter import custom_formatter


def main():
    root = tk.Tk()
    PoTraApp(root, formatter=custom_formatter)
    root.mainloop()


if __name__ == "__main__":
    main()
