import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import sys
from functools import partial
import threading
import queue
import traceback
import transyytg_con

class FunctionRunner:
    """安全执行外部函数的线程管理器"""
    def __init__(self, gui_update_callback):
        self.gui_update = gui_update_callback
        self.result_queue = queue.Queue()
        self.is_running = False

    def run_in_thread(self, func, *args, **kwargs):
        """在子线程中运行函数"""
        if self.is_running:
            return False
        
        self.is_running = True
        threading.Thread(
            target=self._execute_function,
            args=(func, *args),
            kwargs=kwargs,
            daemon=True
        ).start()
        return True

    def _execute_function(self, func, *args, **kwargs):
        """实际执行函数并捕获异常"""
        try:
            result = func(*args, **kwargs)
            self.result_queue.put(("SUCCESS", result))
        except Exception as e:
            self.result_queue.put(("ERROR", traceback.format_exc()))
        finally:
            self.is_running = False

    def check_result(self):
        """检查任务状态（需在主线程定期调用）"""
        while not self.result_queue.empty():
            status, data = self.result_queue.get()
            self.gui_update(status, data)
        return self.is_running

class OutputRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.auto_scroll = True

    def write(self, string):
        self.auto_scroll = (self.text_widget.yview()[1] == 1.0)
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, string)
        if self.auto_scroll:
            self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.update_idletasks()

    def flush(self):
        pass

class Application:
    def __init__(self, root):
        self.root = root
        self.root.title("DCS任务翻译工具")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化按钮列表
        self.control_buttons = []
        self.run_button = None
        
        self.setup_ui()
        
        self.runner = FunctionRunner(self.handle_function_result)
        self.poll_task_status()

    def setup_ui(self):
        # 主框架
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧输入区
        self.left_frame = tk.Frame(self.main_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 右侧输出区
        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 创建输入字段
        self.create_input_fields()
        
        # 创建输出窗口
        self.create_output_window()
        
        # 重定向输出
        sys.stdout = OutputRedirector(self.output_text)
        print("程序已启动...\n")
        
    def poll_task_status(self):
        """每100ms检查一次任务状态"""
        if self.runner.check_result():
            self.root.after(100, self.poll_task_status)

    def create_input_fields(self):
        # 定义输入字段配置
        fields_config = [
            ("api_key", "sk-xxxxxx", "entry", None),
            ("base_url", "https://api.deepseek.com", "entry", None),
            ("model", "deepseek-chat", "entry", None),
            ("hint", "你是一个翻译，下面是跟战斗机任务（DCS模拟飞行游戏）想关的英语，翻译成简体中文，不要使用markdown输出, 保持原文的换行格式，仅作为翻译不要续写，原文和翻译词数不能相差过大。", "text", None),
            ("remove_json", False, "radio", {"options": ["是", "否"]}),
            ("只输出翻译", False, "radio", {"options": ["是", "否"]}),
            ("路径", "E:\\Eagle Dynamics\\DCS World\\Mods\\campaigns\\FA-18C Raven One", "folder", None),
        ]
        
        self.entries = []
        for i, (label_text, default_value, field_type, options) in enumerate(fields_config):
            tk.Label(self.left_frame, text=label_text).grid(row=i, column=0, padx=5, pady=5, sticky=tk.NE)
            
            if field_type == "entry":
                entry = tk.Entry(self.left_frame)
                entry.insert(0, default_value)
                entry.grid(row=i, column=1, padx=5, pady=5, sticky=tk.EW)
                self.entries.append(("entry", entry))
                
            elif field_type == "text":
                entry = scrolledtext.ScrolledText(self.left_frame, wrap=tk.WORD, width=20, height=4)
                entry.insert(tk.END, default_value)
                entry.grid(row=i, column=1, padx=5, pady=5, sticky=tk.NSEW)
                self.entries.append(("text", entry))
                
            elif field_type == "radio":
                var = tk.BooleanVar(value=default_value)
                frame = tk.Frame(self.left_frame)
                
                for j, option in enumerate(options["options"]):
                    radio = tk.Radiobutton(
                        frame, 
                        text=option,
                        variable=var,
                        value=(option == "是")
                    )
                    radio.pack(side=tk.LEFT, padx=5)
                
                frame.grid(row=i, column=1, padx=5, pady=5, sticky=tk.W)
                self.entries.append(("radio", var))
                
            elif field_type == "folder":
                folder_frame = tk.Frame(self.left_frame)
                
                folder_var = tk.StringVar(value=default_value)
                entry = tk.Entry(folder_frame, textvariable=folder_var, state='readonly')
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
                
                browse_btn = tk.Button(
                    folder_frame, 
                    text="浏览...",
                    command=lambda v=folder_var: self.select_folder(v)
                )
                browse_btn.pack(side=tk.RIGHT)
                
                folder_frame.grid(row=i, column=1, padx=5, pady=5, sticky=tk.EW)
                self.entries.append(("folder", folder_var))
                
                self.control_buttons.append(browse_btn)
        
        # 添加功能按钮
        buttons_frame = tk.Frame(self.left_frame)
        buttons_frame.grid(row=len(fields_config)+2, column=0, columnspan=2, pady=10, sticky=tk.EW)
        
        submit_btn = tk.Button(buttons_frame, text="提交", command=self.on_submit)
        submit_btn.pack(side=tk.LEFT, expand=True, padx=5)
        self.control_buttons.append(submit_btn)
        
        reset_btn = tk.Button(buttons_frame, text="重置", command=self.reset_fields)
        reset_btn.pack(side=tk.LEFT, expand=True, padx=5)
        # self.control_buttons.append(reset_btn)
        
        # 添加运行按钮
        run_btn = tk.Button(buttons_frame, text="运行", command=self.run_process)
        run_btn.config(state=tk.DISABLED)  # 初始禁用
        run_btn.pack(side=tk.LEFT, expand=True, padx=5)
        self.control_buttons.append(run_btn)
        self.run_button = run_btn
        
        self.left_frame.grid_columnconfigure(1, weight=1)
        self.left_frame.grid_rowconfigure(3, weight=1)

    def select_folder(self, folder_var):
        """打开文件夹选择对话框"""
        folder_path = filedialog.askdirectory(title="选择文件夹")
        if folder_path:
            folder_var.set(folder_path)
            print(f"已选择文件夹: {folder_path}")

    def create_output_window(self):
        tk.Label(self.right_frame, text="输出窗口:").pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        self.output_text = scrolledtext.ScrolledText(
            self.right_frame, wrap=tk.WORD, width=40, height=20, state=tk.DISABLED)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # def on_scroll(event):
        #     if hasattr(sys.stdout, 'auto_scroll'):
        #         sys.stdout.auto_scroll = (self.output_text.yview()[1] == 1.0)
        
        # self.output_text.bind("<MouseWheel>", on_scroll)
        # self.output_text.bind("<Button-4>", on_scroll)
        # self.output_text.bind("<Button-5>", on_scroll)
        
        clear_btn = tk.Button(self.right_frame, text="清空输出", command=self.clear_output)
        clear_btn.pack(pady=(0, 5))
        # self.control_buttons.append(clear_btn)

    def toggle_buttons_state(self, state):
        """切换所有控制按钮的状态"""
        for btn in self.control_buttons:
            btn.config(state=state)
        self.root.update_idletasks()

    def run_process(self):
        """运行处理过程"""
        # 获取文本内容和文件夹路径
        api_key = self.entries[0][1].get()  # 第1项是API密钥
        base_url = self.entries[1][1].get()
        model = self.entries[2][1].get()  # 第3项是模型
        hint = self.entries[3][1].get("1.0", tk.END).strip()
        remove_json = self.entries[4][1].get()  # 第5项是是否删除json
        only_output = self.entries[5][1].get()
        folder_path = self.entries[6][1].get()  # 第7项是文件夹
        
        # 检查是否为空
        if not api_key or not base_url or not model or not hint or not folder_path:
            messagebox.showwarning("警告", "不能为空！")
            return
        
        external_func = partial(
            transyytg_con.transyytg_con,
            api_key, base_url, model, hint, remove_json, folder_path, only_output,
        )
        
        if self.runner.run_in_thread(external_func):
            print("开始执行外部函数...")
            self.toggle_buttons_state(tk.DISABLED)
            self.run_button.config(text="运行中...")
            self.poll_task_status()
        # 冻结其他按钮
        
        # if not self.task_handler.start_task(
        #     transyytg_con.transyytg_con,
        #     api_key, base_url, model, hint, remove_json, folder_path, only_output
        # ):
        #     return
        # self.toggle_buttons_state(tk.DISABLED)
        # self.run_button.config(text="运行中...")
        # print("\n开始运行处理...")
        # # 模拟调用外部函数
        # try:
        #     transyytg_con.transyytg_con(api_key, base_url, model, hint, remove_json, folder_path, only_output)
        # except Exception as e:
        #     print(f"运行出错: {str(e)}")
        # finally:
        #     # 恢复按钮状态
        #     self.toggle_buttons_state(tk.NORMAL)
        #     self.run_button.config(text="运行")
    

    def handle_function_result(self, status, data):
        """处理函数执行结果"""
        if status == "PROGRESS":
            print(data)
        elif status == "SUCCESS":
            print(f"函数执行成功！结果: {data}")
            self.toggle_buttons_state(tk.NORMAL)
            self.run_button.config(text="运行")
        elif status == "ERROR":
            print(f"函数执行失败！错误:\n{data}")
            messagebox.showerror("错误", "函数执行异常")
            self.toggle_buttons_state(tk.NORMAL)
            self.run_button.config(text="运行")
    

    def on_submit(self):
        values = []
        for entry_type, entry in self.entries:
            if entry_type == "entry":
                values.append(entry.get())
            elif entry_type == "text":
                values.append(entry.get("1.0", tk.END).strip())
            elif entry_type == "radio":
                values.append("是" if entry.get() else "否")
            elif entry_type == "folder":
                values.append(entry.get())
        
        print("\n提交的数据:")
        for i, value in enumerate(values, 1):
            print(f"输入{i}: {value}")
        print("-" * 30)
        self.toggle_buttons_state(tk.NORMAL)

    def reset_fields(self):
        defaults = [
            ("user123", "entry"),
            ("password", "entry"),
            ("example@domain.com", "entry"),
            ("多行文本输入区\n示例文本", "text"),
            (True, "radio"),
            (False, "radio"),
            ("默认备注信息", "entry")
        ]
        
        for (entry_type, entry), (default_value, _) in zip(self.entries, defaults):
            if entry_type == "entry":
                entry.delete(0, tk.END)
                entry.insert(0, default_value)
            elif entry_type == "text":
                entry.delete("1.0", tk.END)
                entry.insert(tk.END, default_value)
            elif entry_type == "radio":
                entry.set(default_value)
            elif entry_type == "folder":
                entry.set(default_value)
        
        print("所有输入框已重置为默认值\n")

    def clear_output(self):
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        print("输出窗口已清空\n")

    def on_closing(self):
        sys.stdout = sys.__stdout__
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = Application(root)
    print("本软件为翻译DCS任务文件的工具，使用大模型 API进行翻译，使用前请阅读软件使用说明.txt")
    print("作者：YATEIFEI（https://github.com/YaTaiphy/）")
    print("联系方式：l476579487@126.com")
    root.mainloop()