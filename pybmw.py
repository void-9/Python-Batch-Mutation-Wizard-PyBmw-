##################################################################
#       Python Batch Mutation Wizard (PyBmw)
#
# Version: 1.0
# Author: Abhinav Singh
# Date: October 12, 2025
#
# Description:
# A PyMOL plugin to perform single or batch mutations with an
# interactive GUI, visual feedback, advanced PDB/Session export,
# CSV import, and interactive rotamer sculpting functionality.
##################################################################

import csv
import os
from collections import defaultdict
from functools import partial
from pymol import cmd, CmdException
from pymol.plugins import addmenuitemqt

try:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QDialogButtonBox,
        QApplication, QGroupBox, QRadioButton, QHBoxLayout, QTableWidget,
        QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
        QAbstractItemView, QSpinBox
    )
    from PyQt5.QtCore import Qt
except ImportError:
    print("PyBmw Error: PyQt5 not found. This plugin requires a PyMOL build with PyQt.")

DEBUG_PYBMW = False
def debug_log(msg):
    if DEBUG_PYBMW:
        print(f"[PyBmw Debug] {msg}")

PYMOL_CAPS = {
    "supports_sculpting": False,
    "sculpt_setting_name": None,
}

def detect_pymol_capabilities():
    debug_log("Detecting PyMOL capabilities...")
    candidates = ["sculpt_iterations", "wizard_sculpt_cycles"]
    try:
        try:
            cmd.get("sculpting")
            PYMOL_CAPS["supports_sculpting"] = True
        except CmdException:
            PYMOL_CAPS["supports_sculpting"] = False
            debug_log("No 'sculpting' setting available.")

        for name in candidates:
            try:
                cmd.get(name)
                PYMOL_CAPS["sculpt_setting_name"] = name
                debug_log(f"Detected sculpt setting: {name}")
                break
            except CmdException:
                continue
    except Exception as e:
        PYMOL_CAPS["supports_sculpting"] = False
        PYMOL_CAPS["sculpt_setting_name"] = None
        debug_log(f"Capability detection error: {e}")

try:
    detect_pymol_capabilities()
except Exception as e:
    debug_log(f"Initial capability detection failed: {e}")

dialog = None

class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super(ExportDialog, self).__init__(parent)
        self.setWindowTitle("Select Export Options")
        layout = QVBoxLayout(self)
        group_box = QGroupBox("File type to save:")
        radio_layout = QVBoxLayout()
        self.pdb_only_radio = QRadioButton("Mutated PDB file only")
        self.session_only_radio = QRadioButton("PyMOL Session file (.pse) only")
        self.both_radio = QRadioButton("Both PDB and Session files")
        self.pdb_only_radio.setChecked(True)
        radio_layout.addWidget(self.pdb_only_radio)
        radio_layout.addWidget(self.session_only_radio)
        radio_layout.addWidget(self.both_radio)
        group_box.setLayout(radio_layout)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(group_box)
        layout.addWidget(self.button_box)

    @staticmethod
    def get_export_options(parent=None):
        dialog = ExportDialog(parent)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            if dialog.pdb_only_radio.isChecked(): return "pdb"
            if dialog.session_only_radio.isChecked(): return "session"
            if dialog.both_radio.isChecked(): return "both"
        return None

class PyBmwPanel(QDialog):
    def __init__(self, parent=None):
        super(PyBmwPanel, self).__init__(parent)
        self.setWindowTitle("Python Batch Mutation Wizard v1.0")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumSize(550, 650)

        self.residues_to_mutate = set()
        self.original_residues = {}
        self.mutated_residue_info = {}
        self.csv_targets = {}
        self.amino_acids = ["ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"]
        self.sorted_residue_list = []
        self.step_index = 0

        self.layout = QVBoxLayout(self)

        mode_groupbox = QGroupBox("1. Mutation Mode")
        mode_layout = QHBoxLayout()
        self.batch_mode_radio = QRadioButton("Batch")
        self.individual_mode_radio = QRadioButton("Individual")
        self.step_mode_radio = QRadioButton("Step-by-Step")
        self.batch_mode_radio.setChecked(True)
        mode_layout.addWidget(self.batch_mode_radio)
        mode_layout.addWidget(self.individual_mode_radio)
        mode_layout.addWidget(self.step_mode_radio)
        mode_groupbox.setLayout(mode_layout)

        refinement_groupbox = QGroupBox("2. Post-Mutation Refinement")
        refinement_layout = QHBoxLayout()
        self.refinement_combo = QComboBox()
        
        refinement_options = ["Wizard Default Rotamer"]
        if PYMOL_CAPS["supports_sculpting"] and PYMOL_CAPS["sculpt_setting_name"]:
            refinement_options.append("Sculpt Rotamer")
        self.refinement_combo.addItems(refinement_options)

        self.sculpt_cycles_spinbox = QSpinBox()
        self.sculpt_cycles_spinbox.setRange(1, 1000)
        self.sculpt_cycles_spinbox.setValue(10)
        self.sculpt_cycles_spinbox.setToolTip("Number of sculpting cycles to run for refinement.")
        self.sculpt_cycles_label = QLabel("Cycles:")
        refinement_layout.addWidget(self.refinement_combo)
        refinement_layout.addWidget(self.sculpt_cycles_label)
        refinement_layout.addWidget(self.sculpt_cycles_spinbox)
        refinement_groupbox.setLayout(refinement_layout)

        self.info_label = QLabel("Select residues and click 'Add to Selection' or import a CSV.")

        self.batch_group = QGroupBox("Batch Controls")
        batch_layout = QVBoxLayout()
        self.batch_aa_dropdown = QComboBox()
        self.batch_aa_dropdown.addItems(self.amino_acids)
        batch_layout.addWidget(QLabel("Mutate all selected residues to:"))
        batch_layout.addWidget(self.batch_aa_dropdown)
        self.batch_group.setLayout(batch_layout)

        self.individual_group = QGroupBox("Individual & Step-by-Step Controls")
        individual_layout = QVBoxLayout()
        self.rotamer_control_group = QGroupBox("Interactive Rotamer Selection")
        rotamer_layout = QHBoxLayout()
        self.prev_rotamer_button = QPushButton("◀ Previous")
        self.next_rotamer_button = QPushButton("Next ▶")
        self.rotamer_info_label = QLabel("Rotamer: - / -")
        self.rotamer_info_label.setAlignment(Qt.AlignCenter)
        rotamer_layout.addWidget(self.prev_rotamer_button)
        rotamer_layout.addWidget(self.rotamer_info_label)
        rotamer_layout.addWidget(self.next_rotamer_button)
        self.rotamer_control_group.setLayout(rotamer_layout)

        self.individual_table = QTableWidget()
        self.individual_table.setColumnCount(2)
        self.individual_table.setHorizontalHeaderLabels(["Residue", "Mutate To"])
        self.individual_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.individual_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.individual_table.setSelectionMode(QAbstractItemView.SingleSelection)

        individual_layout.addWidget(self.rotamer_control_group)
        individual_layout.addWidget(self.individual_table)
        self.individual_group.setLayout(individual_layout)

        self.step_control_box = QHBoxLayout()
        self.prev_step_button = QPushButton("<< Previous Residue")
        self.apply_step_button = QPushButton("Apply This Mutation")
        self.next_step_button = QPushButton("Next Residue >>")
        self.step_control_box.addWidget(self.prev_step_button)
        self.step_control_box.addWidget(self.apply_step_button)
        self.step_control_box.addWidget(self.next_step_button)

        self.button_box = QDialogButtonBox()
        self.import_csv_button = self.button_box.addButton("Import CSV...", QDialogButtonBox.ActionRole)
        self.add_button = self.button_box.addButton("Add to Selection", QDialogButtonBox.ActionRole)
        self.clear_all_button = self.button_box.addButton("Clear All", QDialogButtonBox.DestructiveRole)
        self.export_button = self.button_box.addButton("Export Files...", QDialogButtonBox.ActionRole)
        self.mutate_all_button = self.button_box.addButton("Mutate All", QDialogButtonBox.AcceptRole)
        self.cancel_button = self.button_box.addButton(QDialogButtonBox.Cancel)

        self.layout.addWidget(mode_groupbox)
        self.layout.addWidget(refinement_groupbox)
        self.layout.addWidget(self.info_label)
        self.layout.addWidget(self.batch_group)
        self.layout.addWidget(self.individual_group)
        self.layout.addLayout(self.step_control_box)
        self.layout.addWidget(self.button_box)

        self.batch_mode_radio.toggled.connect(self.refresh_panel_view)
        self.individual_mode_radio.toggled.connect(self.refresh_panel_view)
        self.step_mode_radio.toggled.connect(self.refresh_panel_view)
        self.refinement_combo.currentIndexChanged.connect(self.refresh_panel_view)
        self.add_button.clicked.connect(self.update_residue_table)
        self.clear_all_button.clicked.connect(self.full_reset)
        self.import_csv_button.clicked.connect(self.load_mutations_from_csv)
        self.mutate_all_button.clicked.connect(self.start_mutation_process)
        self.export_button.clicked.connect(self.handle_export)
        self.cancel_button.clicked.connect(self.reject)
        self.prev_step_button.clicked.connect(self.show_previous_residue)
        self.apply_step_button.clicked.connect(self.apply_single_mutation_step)
        self.next_step_button.clicked.connect(self.show_next_residue)
        self.individual_table.itemSelectionChanged.connect(self.prime_wizard_from_table_selection)
        self.prev_rotamer_button.clicked.connect(self._previous_rotamer)
        self.next_rotamer_button.clicked.connect(self._next_rotamer)

        self.full_reset()

    def _residue_sort_key(self, res_tuple):
        model, chain, resi_str = res_tuple
        num_part = ''.join(filter(str.isdigit, resi_str))
        char_part = ''.join(filter(str.isalpha, resi_str))
        return (model, chain, int(num_part) if num_part else 0, char_part)

    def _reset_staged_list(self):
        try:
            cmd.delete("highlight_sele")
            cmd.delete("chain_highlight_*")
        except Exception:
            pass

        if self.mutated_residue_info:
            mutated_sele = " or ".join([f"/{r[0]}//{r[1]}/{r[2]}" for r in self.mutated_residue_info.keys()])
            try:
                cmd.color("cyan", mutated_sele)
            except Exception:
                pass

        self.residues_to_mutate = set()
        self.sorted_residue_list = []
        self.original_residues = {k: v for k, v in self.original_residues.items() if k in self.mutated_residue_info}
        try:
            self.individual_table.setRowCount(0)
        except Exception:
            pass
        total_mutated = len(self.mutated_residue_info)
        self.info_label.setText(f"{total_mutated} mutations applied. Select new residues.")
        self.refresh_panel_view()

    def full_reset(self, preserve_selection=False):
        try:
            cmd.delete("highlight_sele")
            cmd.delete("mutated_residues")
            cmd.delete("chain_highlight_*")
        except Exception:
            pass
        if not preserve_selection:
            try:
                cmd.select("none")
            except Exception:
                pass
        try:
            for obj in cmd.get_object_list('(all)'):
                try:
                    cmd.util.cbag(obj)
                except Exception:
                    pass
            cmd.label(selection="all", expression='""')
        except Exception:
            pass

        self.residues_to_mutate = set()
        self.sorted_residue_list = []
        self.original_residues = {}
        self.mutated_residue_info = {}
        self.csv_targets = {}
        self.step_index = 0
        self.info_label.setText("Ready. Select residues and click 'Add to Selection'.")
        try:
            self.individual_table.setRowCount(0)
        except Exception:
            pass
        self.refresh_panel_view()

    def refresh_panel_view(self):
        is_batch = self.batch_mode_radio.isChecked()
        is_individual = self.individual_mode_radio.isChecked()
        is_step = self.step_mode_radio.isChecked()
        is_sculpt = "Sculpt" in self.refinement_combo.currentText()

        self.batch_group.setVisible(is_batch)
        self.individual_group.setVisible(is_individual or is_step)
        self.mutate_all_button.setVisible(is_batch or is_individual)
        self.sculpt_cycles_label.setVisible(is_sculpt and PYMOL_CAPS["supports_sculpting"])
        self.sculpt_cycles_spinbox.setVisible(is_sculpt and PYMOL_CAPS["supports_sculpting"])
        self.rotamer_control_group.setVisible(is_step)

        for i in range(self.step_control_box.count()):
            widget = self.step_control_box.itemAt(i).widget()
            if widget:
                widget.setVisible(is_step)

        if is_step:
            self._update_rotamer_label()

        has_mutations_to_stage = bool(self.residues_to_mutate)
        has_completed_mutations = bool(self.mutated_residue_info)
        self.mutate_all_button.setEnabled(has_mutations_to_stage)
        self.clear_all_button.setEnabled(has_mutations_to_stage or has_completed_mutations)
        self.export_button.setEnabled(has_completed_mutations or bool(cmd.get_object_list('(all)')))

        if is_step:
            has_residues = bool(self.sorted_residue_list)
            self.apply_step_button.setEnabled(has_residues)
            self.prev_step_button.setEnabled(has_residues and self.step_index > 0)
            self.next_step_button.setEnabled(has_residues and self.step_index < len(self.sorted_residue_list) - 1)
            if has_residues and len(self.sorted_residue_list) > self.step_index:
                self.individual_table.selectRow(self.step_index)

    def _update_rotamer_label(self):
        if not self.step_mode_radio.isChecked():
            self.rotamer_info_label.setText("Rotamer: - / -")
            return
        try:
            if cmd.get_wizard():
                current_state = cmd.get_state()
                total_states = cmd.count_frames()
                if total_states > 0:
                    self.rotamer_info_label.setText(f"Rotamer: {current_state} / {total_states}")
                else:
                    self.rotamer_info_label.setText("Rotamer: 1 / 1")
            else:
                 self.rotamer_info_label.setText("Rotamer: - / -")
        except Exception as e:
            debug_log(f"_update_rotamer_label error: {e}")
            self.rotamer_info_label.setText("Rotamer: Error")

    def _previous_rotamer(self):
        try:
            cmd.backward()
        except Exception as e:
            debug_log(f"backward() failed: {e}")
        self._update_rotamer_label()

    def _next_rotamer(self):
        try:
            cmd.forward()
        except Exception as e:
            debug_log(f"forward() failed: {e}")
        self._update_rotamer_label()

    def load_mutations_from_csv(self):
        self.full_reset()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Mutations CSV", "", "CSV Files (*.csv);;All Files (*)")
        if not fileName: return
        all_objects = cmd.get_object_list('(all)')
        if not all_objects:
            QMessageBox.critical(self, "Error", "No molecular objects are loaded in PyMOL.")
            return
        self.csv_targets = {}
        found_residues = set()
        not_found = []
        try:
            with open(fileName, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) < 2: continue
                    location, new_aa = row[0].strip(), row[1].strip().upper()
                    if new_aa not in self.amino_acids:
                        not_found.append(f"Row '{','.join(row)}': '{new_aa}' is not a valid amino acid code.")
                        continue
                    parts = location.replace('/', ' ').split()
                    if len(parts) < 2:
                        not_found.append(f"Row '{','.join(row)}': Location format '{location}' is invalid. Use Chain ResID (e.g., A 123).")
                        continue
                    chain, resi = parts[0], parts[1]
                    found_model = None
                    for obj in all_objects:
                        try:
                            if cmd.count_atoms(f"/{obj}//{chain}/{resi} and polymer") > 0:
                                found_model = obj
                                break
                        except Exception:
                            continue
                    if found_model:
                        res_tuple = (found_model, chain, resi)
                        found_residues.add(res_tuple)
                        self.csv_targets[res_tuple] = new_aa
                    else:
                        not_found.append(f"Row '{','.join(row)}': Residue {chain}/{resi} not found in any loaded object.")
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Failed to read or parse the CSV file.\nError: {e}")
            return

        if not_found:
            QMessageBox.warning(self, "Parsing Issues", "Some rows could not be processed:\n\n" + "\n".join(not_found))
        if found_residues:
            self.residues_to_mutate.update(found_residues)
            self.individual_mode_radio.setChecked(True)
            self._populate_table()

    def fetch_user_selection(self):
        try:
            if cmd.count_atoms('(sele)') == 0:
                return set()
            selected_set = set()
            cmd.iterate('(sele) and polymer', 'selected_set.add((model, chain, resi))', space={'selected_set': selected_set})
            return set((str(m), str(c), str(r)) for (m,c,r) in selected_set)
        except Exception:
            return set()

    def update_residue_table(self):
        newly_selected = self.fetch_user_selection()
        if not newly_selected:
            if self.mutated_residue_info:
                QMessageBox.information(self, "No Selection", "No new residues were selected.\n\nAfter performing mutations, you may need to click 'Clear All' before starting a new selection.")
            else:
                QMessageBox.information(self, "No Selection", "No new residues were selected in the PyMOL window.")
            return
        self.residues_to_mutate.update(newly_selected)
        self._populate_table()
        try:
            cmd.deselect()
        except Exception:
            pass

    def _populate_table(self):
        if self.residues_to_mutate:
            self.info_label.setText(f"{len(self.residues_to_mutate)} residues staged for mutation.")
            try:
                cmd.delete("highlight_sele")
                cmd.delete("chain_highlight_*")
            except CmdException:
                pass
            
            residues_by_chain = defaultdict(list)
            for res_tuple in self.residues_to_mutate:
                model, chain, resi = res_tuple
                residues_by_chain[(model, chain)].append(res_tuple)

            if len(residues_by_chain) > 1:
                highlight_colors = ["yellow", "lightmagenta", "palecyan", "lightorange", "palegreen", "lightblue", "sand", "wheat"]
                color_index = 0
                for (model, chain), residues in residues_by_chain.items():
                    color = highlight_colors[color_index % len(highlight_colors)]
                    color_index += 1
                    sele_name = f"chain_highlight_{model}_{chain}"
                    sele_str = " or ".join([f"/{r[0]}//{r[1]}/{r[2]}" for r in residues])
                    cmd.select(sele_name, sele_str)
                    cmd.color(color, sele_name)
                    
                    first_res_tuple = sorted(residues, key=self._residue_sort_key)[0]
                    label_sele = f"/{first_res_tuple[0]}//{first_res_tuple[1]}/{first_res_tuple[2]} and name CA"
                    cmd.label(label_sele, f'"Chain {chain}"')
            elif self.residues_to_mutate:
                sele_str = " or ".join([f"/{r[0]}//{r[1]}/{r[2]}" for r in self.residues_to_mutate])
                cmd.select("highlight_sele", sele_str)
                cmd.color("yellow", "highlight_sele")

        for res_tuple in self.residues_to_mutate:
            if res_tuple not in self.original_residues:
                model, chain, resi = res_tuple
                my_space = {'resn_list': []}
                try:
                    cmd.iterate(f"/{model}//{chain}/{resi} and name CA", 'resn_list.append(resn)', space=my_space)
                    if my_space['resn_list']:
                        self.original_residues[res_tuple] = my_space['resn_list'][0]
                except Exception:
                    self.original_residues[res_tuple] = "UNK"
        
        self.sorted_residue_list = sorted(list(self.residues_to_mutate), key=self._residue_sort_key)
        
        try:
            self.individual_table.blockSignals(True)
            self.individual_table.setRowCount(len(self.sorted_residue_list))
            for row, res_tuple in enumerate(self.sorted_residue_list):
                resn = self.original_residues.get(res_tuple, "UNK")
                item_text = f"{res_tuple[0]}/{res_tuple[1]}/{resn}{res_tuple[2]}"
                self.individual_table.setItem(row, 0, QTableWidgetItem(item_text))
                combo_box = QComboBox(self.individual_table)
                combo_box.addItems(self.amino_acids)
                if res_tuple in self.csv_targets:
                    combo_box.setCurrentText(self.csv_targets[res_tuple])
                combo_box.currentTextChanged.connect(
                    partial(self.handle_combobox_change, row)
                )
                self.individual_table.setCellWidget(row, 1, combo_box)
        except Exception as e:
            debug_log(f"_populate_table GUI error: {e}")
        finally:
            self.individual_table.blockSignals(False)

        self.refresh_panel_view()

    def handle_combobox_change(self, row, text):
        if self.step_mode_radio.isChecked() and row == self.step_index:
            self.prime_wizard_for_step()

    def prepare_mutagenesis_wizard(self, is_step=False):
        try:
            if not cmd.get_wizard():
                cmd.wizard("mutagenesis")
            cmd.refresh_wizard()
            return True
        except CmdException as e:
            QMessageBox.critical(self, "Error", f"Could not launch PyMOL's mutagenesis wizard.\n{e}")
            return False

    def preview_mutation(self, residue, new_aa):
        model, chain, resi = residue
        selection_string = f"/{model}//{chain}/{resi}"
        try:
            if not self.prepare_mutagenesis_wizard():
                return False
            wizard = cmd.get_wizard()

            if "Sculpt" in self.refinement_combo.currentText() and PYMOL_CAPS["supports_sculpting"]:
                try:
                    cmd.set("sculpting", 1)
                    cycles = self.sculpt_cycles_spinbox.value()
                    sculpt_setting = PYMOL_CAPS["sculpt_setting_name"]
                    if sculpt_setting:
                        cmd.set(sculpt_setting, cycles)
                except Exception as e:
                    debug_log(f"Sculpt enabling error (continuing): {e}")
            else:
                if PYMOL_CAPS["supports_sculpting"]:
                    try:
                        cmd.set("sculpting", 0)
                    except Exception:
                        pass
            
            wizard.do_select(selection_string)
            wizard.set_mode(new_aa)
            cmd.refresh_wizard()
            return True
        except Exception as e:
            if "unknown Setting" not in str(e):
                debug_log(f"Error priming wizard for {selection_string}: {e}")
            return False

    def execute_mutation(self, residue, new_amino_acid):
        if not self.preview_mutation(residue, new_amino_acid):
            return False
        try:
            wizard = cmd.get_wizard()
            wizard.apply()
            self._record_mutation(residue, new_amino_acid)
            return True
        except Exception as e:
            debug_log(f"Failed to mutate {residue}. Error: {e}")
            return False

    def run_all_mutations(self):
        if not self.prepare_mutagenesis_wizard():
            return None

        skipped = []
        for row, residue in enumerate(list(self.sorted_residue_list)):
            try:
                new_aa = self.batch_aa_dropdown.currentText() if self.batch_mode_radio.isChecked() else self.individual_table.cellWidget(row, 1).currentText()
                ok = self.execute_mutation(residue, new_aa)
                if not ok:
                    skipped.append(residue)
            except Exception as e:
                debug_log(f"Error during mutation loop: {e}")
                skipped.append(residue)

        self.finalize_and_cleanup(finish_run=True)
        return skipped

    def start_mutation_process(self):
        num_to_mutate = len(self.sorted_residue_list)
        if num_to_mutate == 0:
            QMessageBox.warning(self, "No Mutations", "No mutations are staged to be applied.")
            return

        skipped_mutations = self.run_all_mutations()
        if skipped_mutations is None:
            return

        num_skipped = len(skipped_mutations)
        num_succeeded = num_to_mutate - num_skipped
        message = f"{num_succeeded} mutation(s) applied successfully."
        if num_skipped > 0:
            message += f"\n{num_skipped} mutation(s) were skipped (see console for details)."
        if num_succeeded > 0:
            QMessageBox.information(self, "Process Complete", message)
        else:
            QMessageBox.warning(self, "Process Failed", message)

        self._reset_staged_list()

    def apply_single_mutation_step(self):
        if not self.sorted_residue_list or self.step_index >= len(self.sorted_residue_list):
            return
        
        residue = self.sorted_residue_list[self.step_index]
        new_aa = self.individual_table.cellWidget(self.step_index, 1).currentText()

        if self.execute_mutation(residue, new_aa):
            if self.sorted_residue_list:
                self.prime_wizard_for_step()
            else:
                self.info_label.setText("All staged mutations have been applied.")
        else:
            QMessageBox.warning(self, "Mutation Failed", f"Could not apply mutation for {residue} to {new_aa}.")

    def _record_mutation(self, residue, new_aa):
        model, chain, resi = residue
        selection_string = f"/{model}//{chain}/{resi}"
        try:
            cmd.color("cyan", selection_string)
            cmd.show("sticks", selection_string)
        except Exception:
            pass
        original_resn = self.original_residues.get(residue, "UNK")
        label_text = f'"{original_resn}{resi} -> {new_aa}"'
        try:
            cmd.label(f"{selection_string} and name CA", label_text)
        except Exception:
            pass
        self.mutated_residue_info[residue] = new_aa
        
        is_step_mode = self.step_mode_radio.isChecked()
        current_residue_at_index = self.sorted_residue_list[self.step_index] if is_step_mode else None

        if residue in self.residues_to_mutate:
            self.residues_to_mutate.remove(residue)
        
        self._populate_table()

        if is_step_mode:
            try:
                self.step_index = self.sorted_residue_list.index(current_residue_at_index)
            except ValueError:
                if self.step_index >= len(self.sorted_residue_list):
                    self.step_index = max(0, len(self.sorted_residue_list) - 1)

        self.info_label.setText(f"{len(self.mutated_residue_info)} total mutations applied.")
        self.refresh_panel_view()

    def show_previous_residue(self):
        if self.step_index > 0:
            self.step_index -= 1
            self.refresh_panel_view()
            self.prime_wizard_for_step()

    def show_next_residue(self):
        if self.step_index < len(self.sorted_residue_list) - 1:
            self.step_index += 1
            self.refresh_panel_view()
            self.prime_wizard_for_step()

    def prime_wizard_from_table_selection(self):
        if not self.step_mode_radio.isChecked(): return
        selected_rows = self.individual_table.selectionModel().selectedRows()
        if not selected_rows: return
        self.step_index = selected_rows[0].row()
        self.refresh_panel_view()
        self.prime_wizard_for_step()

    def prime_wizard_for_step(self):
        if not self.step_mode_radio.isChecked() or not self.sorted_residue_list: return
        if self.step_index >= len(self.sorted_residue_list): return
        if not self.prepare_mutagenesis_wizard(is_step=True): return
        
        residue = self.sorted_residue_list[self.step_index]
        new_aa = self.individual_table.cellWidget(self.step_index, 1).currentText()
        
        if self.preview_mutation(residue, new_aa):
            self._update_rotamer_label()
        else:
            self.rotamer_info_label.setText("Rotamer: N/A")

    def scan_for_steric_clashes(self):
        if not self.mutated_residue_info: return 0
        mutated_sele = " or ".join([f"/{r[0]}//{r[1]}/{r[2]}" for r in self.mutated_residue_info.keys()])
        surround_sele = f"byres ({mutated_sele}) around 5"
        try:
            clashes = cmd.find_pairs(mutated_sele, f"not ({mutated_sele}) and ({surround_sele})", mode=1, cutoff=-0.6)
            return len(clashes)
        except Exception:
            return 0

    def finalize_and_cleanup(self, finish_run=False):
        try:
            if cmd.get_wizard():
                if not self.step_mode_radio.isChecked() or finish_run:
                    try:
                        cmd.set_wizard()
                    except Exception:
                        pass
            if self.mutated_residue_info:
                try:
                    cmd.select("mutated_residues", " or ".join([f"/{r[0]}//{r[1]}/{r[2]}" for r in self.mutated_residue_info.keys()]))
                except Exception:
                    pass
            try:
                cmd.delete("highlight_sele")
                cmd.delete("chain_highlight_*")
            except Exception:
                pass
            if not finish_run:
                try:
                    cmd.deselect()
                except Exception:
                    pass
            try:
                cmd.set("label_color", "white")
                cmd.set("label_size", -0.8)
            except Exception:
                pass
        except Exception:
            pass

    def handle_export(self):
        if not self.mutated_residue_info:
            reply = QMessageBox.question(self, "No Mutations Found", "No mutations have been applied yet.\n\nDo you still want to export the current state?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        if self.scan_for_steric_clashes() > 0:
            reply = QMessageBox.warning(self, "Clash Warning", "Severe steric clashes detected. It is recommended to fix these before exporting.\n\nDo you want to export anyway?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return
        
        all_objects = cmd.get_object_list('(all)')
        if not all_objects:
            QMessageBox.critical(self, "Error", "No objects loaded to export.")
            return
        object_name = all_objects[0]
        export_choice = ExportDialog.get_export_options(self)
        if not export_choice: return
        
        if export_choice == "both":
            folder_path = QFileDialog.getExistingDirectory(self, "Select Directory to Save Files")
            if folder_path:
                try:
                    pdb_path = os.path.join(folder_path, f"{object_name}_mutated.pdb")
                    session_path = os.path.join(folder_path, f"{object_name}_mutated.pse")
                    pdb_saved = self._save_pdb(object_name, file_path=pdb_path)
                    session_saved = self._save_session(file_path=session_path)
                    if pdb_saved or session_saved:
                        QMessageBox.information(self, "Success", f"Files saved in:\n{folder_path}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not save files. Error: {e}")
        else:
            saved = False
            if export_choice == "pdb": saved = self._save_pdb(object_name)
            elif export_choice == "session": saved = self._save_session()
            if saved: QMessageBox.information(self, "Success", "File saved successfully.")

    def _save_pdb(self, object_name, file_path=None):
        fileName = file_path or QFileDialog.getSaveFileName(self, "Save Mutated PDB", f"{object_name}_mutated.pdb", "PDB Files (*.pdb);;All Files (*)")[0]
        if fileName:
            try:
                cmd.save(fileName, object_name)
                return True
            except Exception as e:
                QMessageBox.critical(self, "PDB Save Error", f"Could not save PDB file. Error: {e}")
        return False

    def _save_session(self, file_path=None):
        fileName = file_path or QFileDialog.getSaveFileName(self, "Save PyMOL Session", "mutated_session.pse", "PyMOL Session Files (*.pse);;All Files (*)")[0]
        if fileName:
            try:
                cmd.save(fileName)
                return True
            except Exception as e:
                QMessageBox.critical(self, "Session Save Error", f"Could not save session file. Error: {e}")
        return False

    def reject(self):
        """Called when the dialog is closed or cancelled."""
        try:
            if cmd.get_wizard():
                cmd.set_wizard()
        except Exception as e:
            debug_log(f"Error closing wizard on exit: {e}")
        
        self.finalize_and_cleanup()
        super(PyBmwPanel, self).reject()

def launch_pybmw_plugin():
    global dialog
    parent = None
    try:
        from pymol.Qt import get_parent_window
        parent = get_parent_window()
    except Exception:
        for widget in QApplication.topLevelWidgets():
            try:
                if widget.isWindow() and "PyMOL" in widget.windowTitle():
                    parent = widget
                    break
            except Exception:
                continue
    if dialog is None:
        dialog = PyBmwPanel(parent)
    
    dialog.full_reset(preserve_selection=True)
    initial_selection = dialog.fetch_user_selection()
    if initial_selection:
        dialog.residues_to_mutate.update(initial_selection)
        dialog._populate_table()
    try:
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    except Exception:
        pass

def __init_plugin__(self=None):
    try:
        detect_pymol_capabilities()
    except Exception as e:
        debug_log(f"Re-detect failed: {e}")
    addmenuitemqt('Python Batch Mutation Wizard (PyBmw)', launch_pybmw_plugin)