"""
gui_app.py
----------
Desktop Graphical User Interface (GUI) for ETABS v23 ↔ DXF Structural Validator.
Uses standard Python tkinter/ttk (zero extra GUI dependencies needed on Windows).
"""

import os
import sys
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Ensure checker modules are accessible
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from config import Config
from phase1_etabs import extract_all, load_from_csvs
from phase2_dxf import parse_dxf
from phase3_validation import validate, Status
from report import generate_reports


class ValidatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ETABS v23 ↔ DXF Structural Validator")
        self.geometry("780x680")
        self.minsize(700, 600)

        # Style configuration
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self._configure_styles()
        self._build_ui()

        # State
        self.dxf_path = tk.StringVar()
        self.scale_var = tk.StringVar(value="0.01 (Centimeters - Default)")
        self.chk_cols = tk.BooleanVar(value=True)
        self.chk_beams = tk.BooleanVar(value=True)
        self.chk_walls = tk.BooleanVar(value=True)
        self.chk_slabs = tk.BooleanVar(value=True)
        self.chk_hinges = tk.BooleanVar(value=True)
        self.chk_materials = tk.BooleanVar(value=True)
        self.chk_loads = tk.BooleanVar(value=True)
        self.chk_restraints = tk.BooleanVar(value=True)

        self.last_pdf = None
        self.last_html = None

    def _configure_styles(self):
        self.configure(bg="#f8f9fa")
        self.style.configure("TLabel", background="#f8f9fa", font=("Segoe UI", 9))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#212529")
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 8), foreground="#6c757d")
        self.style.configure("Card.TFrame", background="#ffffff", relief="groove")
        self.style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground="#ffffff", background="#0d6efd")

    def _build_ui(self):
        # Top Header Banner
        header_frame = tk.Frame(self, bg="#212529", padx=16, pady=12)
        header_frame.pack(fill="x")

        lbl_title = tk.Label(
            header_frame, text="🏗️ ETABS v23 ↔ DXF Structural Validator",
            font=("Segoe UI", 13, "bold"), fg="#ffffff", bg="#212529"
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            header_frame,
            text="Automated Cross-Check: ETABS Model (Property Definitions & Hinges) vs 2D CAD Drawing",
            font=("Segoe UI", 8), fg="#adb5bd", bg="#212529"
        )
        lbl_sub.pack(anchor="w")

        # Main Container
        main_container = tk.Frame(self, bg="#f8f9fa", padx=16, pady=10)
        main_container.pack(fill="both", expand=True)

        # 1. ETABS Connection Status Box
        etabs_box = tk.LabelFrame(main_container, text=" 1. ETABS Connection ", font=("Segoe UI", 9, "bold"), bg="#ffffff", padx=12, pady=8)
        etabs_box.pack(fill="x", pady=4)

        etabs_inner = tk.Frame(etabs_box, bg="#ffffff")
        etabs_inner.pack(fill="x")

        self.lbl_etabs_status = tk.Label(
            etabs_inner, text="⚪ ETABS: Not tested yet. (Open ETABS v23 and click 'Test Connection')",
            font=("Segoe UI", 9), bg="#ffffff", fg="#495057", anchor="w"
        )
        self.lbl_etabs_status.pack(side="left", fill="x", expand=True)

        btn_test_etabs = tk.Button(
            etabs_inner, text="🔌 Test Connection", command=self._on_test_etabs,
            font=("Segoe UI", 8, "bold"), bg="#e9ecef", padx=8, pady=3, relief="groove"
        )
        btn_test_etabs.pack(side="right")

        # 2. DXF File Selection Box
        dxf_box = tk.LabelFrame(main_container, text=" 2. DXF CAD Drawing ", font=("Segoe UI", 9, "bold"), bg="#ffffff", padx=12, pady=8)
        dxf_box.pack(fill="x", pady=4)

        dxf_inner = tk.Frame(dxf_box, bg="#ffffff")
        dxf_inner.pack(fill="x")

        self.ent_dxf = tk.Entry(dxf_inner, font=("Segoe UI", 9), bg="#f8f9fa", relief="solid", bd=1)
        self.ent_dxf.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=3)

        btn_browse = tk.Button(
            dxf_inner, text="📂 Browse DXF...", command=self._on_browse_dxf,
            font=("Segoe UI", 8, "bold"), bg="#0d6efd", fg="#ffffff", padx=10, pady=3, relief="flat"
        )
        btn_browse.pack(side="right")

        btn_sample = tk.Button(
            dxf_inner, text="🧪 Use Sample", command=self._on_use_sample,
            font=("Segoe UI", 8), bg="#e9ecef", padx=6, pady=3, relief="groove"
        )
        btn_sample.pack(side="right", padx=4)

        # 3. Settings & Tolerances Box
        opt_box = tk.LabelFrame(main_container, text=" 3. Validation Settings ", font=("Segoe UI", 9, "bold"), bg="#ffffff", padx=12, pady=8)
        opt_box.pack(fill="x", pady=4)

        # Row 1: Units and Element Checkboxes
        opt_row1 = tk.Frame(opt_box, bg="#ffffff")
        opt_row1.pack(fill="x", pady=2)

        tk.Label(opt_row1, text="CAD Units:", bg="#ffffff", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        self.cbo_scale = ttk.Combobox(
            opt_row1, values=[
                "0.01 (Centimeters - Default)",
                "0.001 (Millimeters)",
                "1.0 (Meters)"
            ], state="readonly", width=25
        )
        self.cbo_scale.current(0)
        self.cbo_scale.pack(side="left", padx=(0, 16))

        tk.Label(opt_row1, text="Elements:", bg="#ffffff", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        tk.Checkbutton(opt_row1, text="Columns", variable=self.chk_cols, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Checkbutton(opt_row1, text="Beams", variable=self.chk_beams, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Checkbutton(opt_row1, text="Walls", variable=self.chk_walls, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Checkbutton(opt_row1, text="Slabs", variable=self.chk_slabs, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Checkbutton(opt_row1, text="Hinges", variable=self.chk_hinges, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Row 2: Model Audits
        opt_row2 = tk.Frame(opt_box, bg="#ffffff")
        opt_row2.pack(fill="x", pady=(4, 0))

        tk.Label(opt_row2, text="Audits:", bg="#ffffff", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        tk.Checkbutton(opt_row2, text="🧪 Materials (fc, fy, E)", variable=self.chk_materials, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=3)
        tk.Checkbutton(opt_row2, text="⚖️ Loads & Multipliers", variable=self.chk_loads, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=3)
        tk.Checkbutton(opt_row2, text="🧱 Supports (Boundary)", variable=self.chk_restraints, bg="#ffffff", font=("Segoe UI", 8)).pack(side="left", padx=3)

        # 4. Action Button Bar
        action_bar = tk.Frame(main_container, bg="#f8f9fa", pady=6)
        action_bar.pack(fill="x")

        self.btn_run = tk.Button(
            action_bar, text="▶ Run Validation Cross-Check", command=self._on_run_validation,
            font=("Segoe UI", 11, "bold"), bg="#198754", fg="#ffffff", activebackground="#157347",
            activeforeground="#ffffff", pady=6, relief="flat", cursor="hand2"
        )
        self.btn_run.pack(fill="x")

        # 5. Live Log Console
        log_box = tk.LabelFrame(main_container, text=" Live Execution Log ", font=("Segoe UI", 8), bg="#ffffff", padx=8, pady=4)
        log_box.pack(fill="both", expand=True, pady=4)

        self.txt_log = tk.Text(log_box, height=10, font=("Consolas", 8), bg="#1e1e1e", fg="#d4d4d4", relief="flat")
        self.txt_log.pack(fill="both", expand=True, side="left")

        scroll = tk.Scrollbar(log_box, command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)

        # 6. Bottom Results Action Bar
        self.res_frame = tk.Frame(self, bg="#e9ecef", padx=16, pady=8)
        self.res_frame.pack(fill="x", side="bottom")

        self.lbl_summary = tk.Label(
            self.res_frame, text="Ready to validate.", font=("Segoe UI", 9, "bold"), bg="#e9ecef", fg="#495057"
        )
        self.lbl_summary.pack(side="left")

        self.btn_open_folder = tk.Button(
            self.res_frame, text="📁 Open Folder", command=self._on_open_folder,
            font=("Segoe UI", 8), bg="#ffffff", relief="groove", state="disabled"
        )
        self.btn_open_folder.pack(side="right", padx=3)

        self.btn_open_html = tk.Button(
            self.res_frame, text="🌐 View HTML", command=self._on_open_html,
            font=("Segoe UI", 8), bg="#ffffff", relief="groove", state="disabled"
        )
        self.btn_open_html.pack(side="right", padx=3)

        self.btn_open_pdf = tk.Button(
            self.res_frame, text="📄 View PDF Report", command=self._on_open_pdf,
            font=("Segoe UI", 8, "bold"), bg="#0d6efd", fg="#ffffff", relief="flat", state="disabled"
        )
        self.btn_open_pdf.pack(side="right", padx=3)

    def _log(self, text):
        self.txt_log.insert("end", text + "\n")
        self.txt_log.see("end")

    def _on_browse_dxf(self):
        filename = filedialog.askopenfilename(
            title="Select 2D DXF Drawing File",
            filetypes=[("AutoCAD DXF Files", "*.dxf"), ("All Files", "*.*")]
        )
        if filename:
            self.ent_dxf.delete(0, "end")
            self.ent_dxf.insert(0, filename)
            self._log(f"Selected DXF: {filename}")

    def _on_use_sample(self):
        sample_path = os.path.join(SCRIPT_DIR, "sample_building.dxf")
        if os.path.exists(sample_path):
            self.ent_dxf.delete(0, "end")
            self.ent_dxf.insert(0, sample_path)
            self._log(f"Loaded sample test model: {sample_path}")
        else:
            messagebox.showwarning("Sample Not Found", "sample_building.dxf not found in script directory.")

    def _on_test_etabs(self):
        self.lbl_etabs_status.config(text="Connecting to ETABS v23...", fg="#b07d00")
        self._log("Testing connection to active ETABS v23 application...")

        def _worker():
            try:
                import comtypes.client
                prog_id = "CSI.ETABS.API.ETABSObject"
                etabs_obj = None

                # Method 1: ETABSv1.Helper
                try:
                    helper = comtypes.client.CreateObject("ETABSv1.Helper")
                    try:
                        import comtypes.gen.ETABSv1 as ETABSv1
                        helper = helper.QueryInterface(ETABSv1.cHelper)
                    except Exception:
                        pass
                    etabs_obj = helper.GetObject(prog_id)
                except Exception:
                    pass

                # Method 2: GetActiveObject
                if etabs_obj is None:
                    etabs_obj = comtypes.client.GetActiveObject(prog_id)

                sap = etabs_obj.SapModel
                ret, fname = sap.GetModelFilename()
                ret_s, n_stories, stories, _ = sap.Story.GetStories()
                ret_f, n_frames, _ = sap.FrameObj.GetNameList()

                model_name = os.path.basename(fname) if fname else "Active Model"
                msg = f"🟢 Connected: {model_name} ({n_stories} Stories, {n_frames} Frames)"
                self.after(0, lambda: self._update_etabs_success(msg))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._update_etabs_fail(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_etabs_success(self, msg):
        self.lbl_etabs_status.config(text=msg, fg="#198754")
        self._log(f"[OK] {msg}")

    def _update_etabs_fail(self, err):
        self.lbl_etabs_status.config(
            text="🔴 Could not connect to ETABS. (Is ETABS open with a model?)",
            fg="#dc3545"
        )
        self._log(f"[ERROR] Could not connect to ETABS: {err}")
        self._log("Tip: If ETABS was started 'As Administrator', launch this app as Administrator too.")

    def _on_run_validation(self):
        dxf_file = self.ent_dxf.get().strip()
        if not dxf_file:
            messagebox.showerror("Missing DXF", "Please select a DXF file first (or click 'Use Sample').")
            return
        if not os.path.exists(dxf_file):
            messagebox.showerror("File Not Found", f"The file does not exist:\n{dxf_file}")
            return

        self.btn_run.config(state="disabled", text="⏳ Running Validation...")
        self.lbl_summary.config(text="Processing...", fg="#b07d00")

        # Parse scale
        scale_txt = self.cbo_scale.get()
        if "Millimeters" in scale_txt:
            scale = 0.001
        elif "Meters" in scale_txt:
            scale = 1.0
        else:
            scale = 0.01

        # Element types
        elem_types = []
        if self.chk_cols.get(): elem_types.append("columns")
        if self.chk_beams.get(): elem_types.append("beams")
        if self.chk_walls.get(): elem_types.append("walls")
        if self.chk_slabs.get(): elem_types.append("slabs")

        report_hinges = self.chk_hinges.get()

        cfg = Config(
            dxf_unit_scale=scale,
            extract_elements=elem_types,
            report_hinges=report_hinges,
            audit_materials=self.chk_materials.get(),
            audit_loads=self.chk_loads.get(),
            audit_restraints=self.chk_restraints.get(),
            html_output=os.path.join(SCRIPT_DIR, "validation_report.html"),
            pdf_output=os.path.join(SCRIPT_DIR, "validation_report.pdf"),
        )

        def _worker():
            try:
                self._log("\n" + "="*50)
                self._log(f"Starting validation for: {os.path.basename(dxf_file)}")
                self._log("="*50)

                # Phase 2: Parse DXF
                self._log("Phase 2: Parsing DXF contours and annotations...")
                df_dxf = parse_dxf(dxf_file, cfg)
                self._log(f"  Found {len(df_dxf)} DXF elements.")

                # Phase 1: ETABS
                # Check if sample mode or live ETABS
                sample_prefix = os.path.join(SCRIPT_DIR, "etabs_sample")
                if "sample_building.dxf" in dxf_file and os.path.exists(f"{sample_prefix}_columns.csv"):
                    self._log("Phase 1: Loading pre-exported sample ETABS data...")
                    etabs_data = load_from_csvs(sample_prefix)
                else:
                    self._log("Phase 1: Extracting live data from ETABS v23...")
                    etabs_data = extract_all(cfg)

                # Phase 3: Validation
                self._log("Phase 3: Cross-referencing geometry and sections...")
                df_result = validate(etabs_data, df_dxf, cfg)

                # Report generation
                self._log("Generating PDF and HTML discrepancy reports...")
                generate_reports(df_result, cfg)

                counts = df_result["status"].value_counts() if not df_result.empty else {}
                m = counts.get(Status.MATCH, 0)
                sm = counts.get(Status.SECTION_MISMATCH, 0)
                eo = counts.get(Status.ETABS_ONLY, 0)
                do = counts.get(Status.DXF_ONLY, 0)

                summary_txt = f"Done! Matches: {m} | Mismatches: {sm} | ETABS Only: {eo} | DXF Only: {do}"
                self.after(0, lambda: self._on_validation_success(cfg, summary_txt))

            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda: self._on_validation_error(err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_validation_success(self, cfg, summary_txt):
        self.btn_run.config(state="normal", text="▶ Run Validation Cross-Check")
        self.lbl_summary.config(text=summary_txt, fg="#198754")
        self._log(f"\n[SUCCESS] {summary_txt}")
        self._log(f"PDF saved: {cfg.pdf_output}")

        self.last_pdf = cfg.pdf_output
        self.last_html = cfg.html_output

        self.btn_open_pdf.config(state="normal")
        self.btn_open_html.config(state="normal")
        self.btn_open_folder.config(state="normal")

        # Automatically pop open the PDF report
        self._on_open_pdf()

    def _on_validation_error(self, err_msg):
        self.btn_run.config(state="normal", text="▶ Run Validation Cross-Check")
        self.lbl_summary.config(text="Validation failed. See log.", fg="#dc3545")
        self._log(f"\n[ERROR] Validation failed: {err_msg}")
        messagebox.showerror("Validation Error", f"An error occurred during validation:\n\n{err_msg}")

    def _on_open_pdf(self):
        if self.last_pdf and os.path.exists(self.last_pdf):
            if sys.platform == "win32":
                os.startfile(self.last_pdf)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.last_pdf])
            else:
                subprocess.Popen(["xdg-open", self.last_pdf])

    def _on_open_html(self):
        if self.last_html and os.path.exists(self.last_html):
            if sys.platform == "win32":
                os.startfile(self.last_html)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.last_html])
            else:
                subprocess.Popen(["xdg-open", self.last_html])

    def _on_open_folder(self):
        if sys.platform == "win32":
            os.startfile(SCRIPT_DIR)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", SCRIPT_DIR])
        else:
            subprocess.Popen(["xdg-open", SCRIPT_DIR])


def main():
    app = ValidatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
