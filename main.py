import customtkinter as ctk
from tkinter import filedialog, messagebox
import ollama
import threading
import json
import os

# === Настройки внешнего вида ===
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# === Константы путей ===
CHATS_DIR = "chats"
CHATS_FILE = os.path.join(CHATS_DIR, "chats.json")
SETTINGS_DIR = "settings"
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "config.json")

# === Модель по умолчанию ===
DEFAULT_MODEL = "hf.co/mradermacher/SAINEMO-reMIX-GGUF:Q8_0"

# === Глобальные переменные ===
chats = {}
current_chat_id = None
config = {
    "theme": "dark",
    "model": DEFAULT_MODEL,
    "temperature": 0.9,
    "top_p": 0.9,
    "max_tokens": 800,
    "repeat_penalty": 1.1,
    "chat_font_size": 12,
    "input_font_size": 12,
    "chat_font_family": "Arial"
}

# === Системный промпт ===
SYSTEM_PROMPT = '''Ты — мастер подземелий (Game Master) в интерактивной текстовой RPG. Твоя задача — создавать захватывающие, детализированные описания мира, персонажей и событий на основе действий игрока. Игрок будет описывать свои действия, а ты должен реагировать, развивая историю. Если пользователь поприветствовал тебя, поприветствуй его в ответ и предложи начать игру.

Правила:
1. Всегда описывай сцену от второго лица («Вы видите...», «Перед вами...»).
2. Отвечай на действия игрока логично и креативно. Если игрок пытается сделать что-то невозможное (например, взлететь без крыльев), объясни, почему это не получается, и предложи альтернативу.
3. Не управляй действиями игрока — только описывай мир и реакции NPC.
4. Поддерживай атмосферу выбранного жанра. По умолчанию жанр — фэнтези, но если игрок захочет сменить сеттинг, подстройся.
5. Включай в описание детали: запахи, звуки, ощущения, чтобы погрузить игрока.
6. Если игрок вводит команду в кавычках (например, «Привет, стражник»), считай это диалогом и отвечай от лица NPC.
7. Не заканчивай историю без явной просьбы игрока. Если сюжет подходит к логическому завершению, предложи игроку выбрать дальнейшее направление.
8. Избегай повторений. Старайся разнообразить описания.
9. Помни предыдущие события и упоминай их, когда это уместно.

Чего делать нельзя:
- Нельзя нарушать четвёртую стену (не говори об AI, не комментируй свою работу как модели).
- Нельзя заменять игрока — не принимай решения за него, не описывай его мысли и чувства (только внешние проявления).
- Нельзя использовать современный сленг или отсылки к реальному миру, если это не соответствует жанру.
- Нельзя вводить слишком много персонажей сразу — это запутывает.
- Нельзя навязывать игроку определённый путь — всегда оставляй свободу выбора.

Пример:
Игрок: Осмотреться
Ты: Вы оглядываетесь. Вокруг тёмный лес, лунный свет пробивается сквозь кроны деревьев. Где-то вдалеке слышен вой волка. У ваших ног лежит старый ржавый меч.

Игрок: Взять меч и пойти на звук
Ты: Вы поднимаете меч — он тяжёлый, но, видимо, ещё пригоден для боя. Вы направляетесь в сторону воя. Через несколько минут вы выходите на поляну, где видите стаю волков, окруживших раненого путника.

Теперь начни игру с краткого вступления, описывающего начальную локацию и задачу. Жанр: фэнтези. Игрок находится у входа в тёмное подземелье. Предложи ему описать свои действия.'''

# === Функции для работы с настройками ===
def ensure_dirs():
    for d in [CHATS_DIR, SETTINGS_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)

def load_config():
    global config
    ensure_dirs()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить настройки: {e}")
    ctk.set_appearance_mode(config.get("theme", "dark"))

def save_config():
    ensure_dirs()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {e}")

# === Функции для работы с чатами ===
def load_chats():
    global chats
    ensure_dirs()
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                chats = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить чаты: {e}")
            chats = {}
    else:
        chats = {}
    if not chats:
        create_new_chat("Чат 1")

def save_chats():
    ensure_dirs()
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось сохранить чаты: {e}")

def create_new_chat(name=None):
    new_id = str(max([int(cid) for cid in chats.keys()] + [0]) + 1)
    if name is None:
        name = f"Чат {new_id}"
    chats[new_id] = {
        "name": name,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}]
    }
    save_chats()
    return new_id

def delete_chat(chat_id):
    if len(chats) <= 1:
        messagebox.showwarning("Внимание", "Нельзя удалить единственный чат.")
        return False
    del chats[chat_id]
    save_chats()
    return True

def rename_chat(chat_id, new_name):
    if chat_id in chats:
        chats[chat_id]["name"] = new_name
        save_chats()
        refresh_chat_panel()
        return True
    return False

# === Функции интерфейса ===
def refresh_chat_panel():
    # Очищаем панель, оставляя только кнопки "Настройки" и "Новый чат"
    for widget in chat_panel.winfo_children():
        widget.destroy()

    for cid, cdata in chats.items():
        frame = ctk.CTkFrame(chat_panel, fg_color="transparent")
        frame.pack(fill="x", pady=2, padx=5)

        # Кнопка с названием чата (переключение + двойной клик для переименования)
        btn = ctk.CTkButton(
            frame,
            text=cdata["name"],
            anchor="w",
            fg_color="#2b2b2b" if cid != current_chat_id else "#1f538d",
            hover_color="#3c3c3c",
            command=lambda cid=cid: load_chat_to_display(cid)
        )
        btn.pack(side="left", fill="x", expand=True)
        btn.bind("<Double-Button-1>", lambda e, cid=cid: rename_chat_dialog(cid))

        # Кнопка переименования (карандаш)
        rename_btn = ctk.CTkButton(
            frame,
            text="✎",
            width=30,
            fg_color="#2b2b2b",
            hover_color="#3c3c3c",
            command=lambda cid=cid: rename_chat_dialog(cid)
        )
        rename_btn.pack(side="right", padx=(2, 0))

        # Кнопка удаления
        del_btn = ctk.CTkButton(
            frame,
            text="✖",
            width=30,
            fg_color="#2b2b2b",
            hover_color="#8b0000",
            command=lambda cid=cid: delete_chat_action(cid)
        )
        del_btn.pack(side="right", padx=(2, 0))

def rename_chat_dialog(chat_id):
    dialog = ctk.CTkInputDialog(text="Введите новое название чата:", title="Переименовать чат")
    new_name = dialog.get_input()
    if new_name and new_name.strip():
        rename_chat(chat_id, new_name.strip())

def load_chat_to_display(chat_id):
    global current_chat_id
    current_chat_id = chat_id
    chat_data = chats[chat_id]

    chat_area.configure(state="normal")
    chat_area.delete("1.0", "end")
    for msg in chat_data["messages"]:
        if msg["role"] == "user":
            chat_area.insert("end", f"Вы: {msg['content']}\n")
        elif msg["role"] == "assistant":
            chat_area.insert("end", f"Модель: {msg['content']}\n\n")
    chat_area.configure(state="disabled")
    chat_area.see("end")

    refresh_chat_panel()

def new_chat_action():
    new_id = create_new_chat()
    refresh_chat_panel()
    load_chat_to_display(new_id)

def delete_chat_action(chat_id):
    if delete_chat(chat_id):
        if chat_id == current_chat_id:
            if chats:
                first_id = next(iter(chats))
                load_chat_to_display(first_id)
            else:
                new_chat_action()
        else:
            refresh_chat_panel()

def send_message():
    if not current_chat_id:
        messagebox.showwarning("Внимание", "Сначала выберите чат.")
        return
    user_input = entry.get()
    if not user_input.strip():
        return

    chat_area.configure(state="normal")
    chat_area.insert("end", f"Вы: {user_input}\n")
    chat_area.see("end")
    chat_area.configure(state="disabled")
    entry.delete(0, "end")

    chats[current_chat_id]["messages"].append({"role": "user", "content": user_input})
    save_chats()

    threading.Thread(target=get_response).start()

def get_response():
    try:
        history = chats[current_chat_id]["messages"]
        response = ollama.chat(
            model=config["model"],
            messages=history,
            options={
                "temperature": config["temperature"],
                "top_p": config["top_p"],
                "max_tokens": config["max_tokens"],
                "repeat_penalty": config["repeat_penalty"]
            }
        )
        assistant_reply = response["message"]["content"]
    except Exception as e:
        assistant_reply = f"Ошибка: {e}"

    root.after(0, display_response, assistant_reply)

def display_response(reply):
    chat_area.configure(state="normal")
    chat_area.insert("end", f"Модель: {reply}\n\n")
    chat_area.see("end")
    chat_area.configure(state="disabled")

    if current_chat_id:
        chats[current_chat_id]["messages"].append({"role": "assistant", "content": reply})
        save_chats()

def load_file():
    file_path = filedialog.askopenfilename(
        title="Выберите текстовый файл",
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    if not file_path:
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        entry.delete(0, "end")
        entry.insert(0, content)
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось прочитать файл:\n{e}")

# === Окно настроек ===
def open_settings():
    settings_window = ctk.CTkToplevel(root)
    settings_window.title("Настройки")
    settings_window.geometry("550x550")
    settings_window.minsize(600, 500)
    settings_window.grab_set()

    tabview = ctk.CTkTabview(settings_window)
    tabview.pack(fill="both", expand=True, padx=10, pady=10)

    # === Вкладка "Интерфейс" (первая) ===
    tab_ui = tabview.add("Интерфейс")
    tabview.set("Интерфейс")  # делаем активной

    # Тема
    ctk.CTkLabel(tab_ui, text="Тема оформления:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    theme_var = ctk.StringVar(value=config["theme"])
    theme_menu = ctk.CTkOptionMenu(tab_ui, values=["dark", "light"], variable=theme_var)
    theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # Размер шрифта области чата
    ctk.CTkLabel(tab_ui, text="Размер шрифта области чата:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
    chat_font_size_slider = ctk.CTkSlider(tab_ui, from_=8, to=24, number_of_steps=16)
    chat_font_size_slider.set(config["chat_font_size"])
    chat_font_size_slider.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    chat_font_size_label = ctk.CTkLabel(tab_ui, text=f"{config['chat_font_size']} pt")
    chat_font_size_label.grid(row=1, column=2, padx=5)
    def update_chat_font(val):
        chat_font_size_label.configure(text=f"{int(val)} pt")
    chat_font_size_slider.configure(command=update_chat_font)

    # Размер шрифта поля ввода
    ctk.CTkLabel(tab_ui, text="Размер шрифта поля ввода:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
    input_font_size_slider = ctk.CTkSlider(tab_ui, from_=8, to=24, number_of_steps=16)
    input_font_size_slider.set(config["input_font_size"])
    input_font_size_slider.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
    input_font_size_label = ctk.CTkLabel(tab_ui, text=f"{config['input_font_size']} pt")
    input_font_size_label.grid(row=2, column=2, padx=5)
    def update_input_font(val):
        input_font_size_label.configure(text=f"{int(val)} pt")
    input_font_size_slider.configure(command=update_input_font)

    # === Вкладка "Модель" ===
    tab_model = tabview.add("Модель")

    ctk.CTkLabel(tab_model, text="Название модели:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    model_entry = ctk.CTkEntry(tab_model, width=300)
    model_entry.insert(0, config["model"])
    model_entry.grid(row=0, column=1, padx=10, pady=10)

    ctk.CTkLabel(tab_model, text="Temperature:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
    temp_slider = ctk.CTkSlider(tab_model, from_=0.0, to=2.0, number_of_steps=20)
    temp_slider.set(config["temperature"])
    temp_slider.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
    temp_label = ctk.CTkLabel(tab_model, text=f"{config['temperature']:.2f}")
    temp_label.grid(row=1, column=2, padx=5)
    def update_temp(val):
        temp_label.configure(text=f"{float(val):.2f}")
    temp_slider.configure(command=update_temp)

    ctk.CTkLabel(tab_model, text="Top_p:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
    top_p_slider = ctk.CTkSlider(tab_model, from_=0.0, to=1.0, number_of_steps=20)
    top_p_slider.set(config["top_p"])
    top_p_slider.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
    top_p_label = ctk.CTkLabel(tab_model, text=f"{config['top_p']:.2f}")
    top_p_label.grid(row=2, column=2, padx=5)
    def update_top_p(val):
        top_p_label.configure(text=f"{float(val):.2f}")
    top_p_slider.configure(command=update_top_p)

    ctk.CTkLabel(tab_model, text="Max tokens:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
    max_tokens_entry = ctk.CTkEntry(tab_model, width=100)
    max_tokens_entry.insert(0, str(config["max_tokens"]))
    max_tokens_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")

    ctk.CTkLabel(tab_model, text="Repeat penalty:").grid(row=4, column=0, padx=10, pady=10, sticky="w")
    penalty_slider = ctk.CTkSlider(tab_model, from_=1.0, to=2.0, number_of_steps=20)
    penalty_slider.set(config["repeat_penalty"])
    penalty_slider.grid(row=4, column=1, padx=10, pady=10, sticky="ew")
    penalty_label = ctk.CTkLabel(tab_model, text=f"{config['repeat_penalty']:.2f}")
    penalty_label.grid(row=4, column=2, padx=5)
    def update_penalty(val):
        penalty_label.configure(text=f"{float(val):.2f}")
    penalty_slider.configure(command=update_penalty)

    # Кнопки сохранения
    def save_settings():
        config["theme"] = theme_var.get()
        config["model"] = model_entry.get().strip()
        config["temperature"] = float(temp_slider.get())
        config["top_p"] = float(top_p_slider.get())
        try:
            config["max_tokens"] = int(max_tokens_entry.get())
        except ValueError:
            messagebox.showerror("Ошибка", "Max tokens должно быть целым числом")
            return
        config["repeat_penalty"] = float(penalty_slider.get())
        config["chat_font_size"] = int(chat_font_size_slider.get())
        config["input_font_size"] = int(input_font_size_slider.get())

        ctk.set_appearance_mode(config["theme"])
        chat_area.configure(font=(config["chat_font_family"], config["chat_font_size"]))
        entry.configure(font=(config["chat_font_family"], config["input_font_size"]))

        save_config()
        settings_window.destroy()
        messagebox.showinfo("Настройки", "Настройки сохранены.")

    save_btn = ctk.CTkButton(settings_window, text="Сохранить", command=save_settings)
    save_btn.pack(pady=10)

# === Создание интерфейса ===
root = ctk.CTk()
root.title("Локальный чат с нейросетью (SAINEMO-reMIX Q8_0)")
root.geometry("900x600")
root.minsize(800, 500)

# Левая панель
left_frame = ctk.CTkFrame(root, width=250)
left_frame.pack(side="left", fill="y", padx=5, pady=5)

settings_btn = ctk.CTkButton(left_frame, text="⚙ Настройки", command=open_settings)
settings_btn.pack(pady=5, padx=10, fill="x")

new_chat_btn = ctk.CTkButton(left_frame, text="+ Новый чат", command=new_chat_action)
new_chat_btn.pack(pady=5, padx=10, fill="x")

chat_panel = ctk.CTkScrollableFrame(left_frame, fg_color="transparent")
chat_panel.pack(fill="both", expand=True, padx=5, pady=5)

# Правая панель
right_frame = ctk.CTkFrame(root)
right_frame.pack(side="right", fill="both", expand=True, padx=5, pady=5)

chat_area = ctk.CTkTextbox(right_frame, wrap="word", state="disabled")
chat_area.pack(padx=10, pady=10, fill="both", expand=True)

input_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
input_frame.pack(padx=10, pady=10, fill="x")

load_btn = ctk.CTkButton(input_frame, text="📁 Загрузить файл", command=load_file, width=120)
load_btn.pack(side="left", padx=(0, 5))

entry = ctk.CTkEntry(input_frame, placeholder_text="Введите сообщение...")
entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
entry.bind("<Return>", lambda event: send_message())

send_btn = ctk.CTkButton(input_frame, text="Отправить", command=send_message, width=100)
send_btn.pack(side="right")

# Инициализация
load_config()
chat_area.configure(font=(config["chat_font_family"], config["chat_font_size"]))
entry.configure(font=(config["chat_font_family"], config["input_font_size"]))

load_chats()
refresh_chat_panel()
if chats:
    first_id = next(iter(chats))
    load_chat_to_display(first_id)

root.mainloop()