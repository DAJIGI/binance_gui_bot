import tkinter as tk

root = tk.Tk()
root.title("테스트 GUI")
root.geometry("300x200")

label = tk.Label(root, text="테스트 창입니다!")
label.pack(pady=20)

root.mainloop()
