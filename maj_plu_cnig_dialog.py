# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import QDate
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from qgis.core import QgsMapLayer, QgsProject


class MajPluCnigDialog(QDialog):
    """Boîte de dialogue principale du plugin MAJ PLU CNIG."""

    PROCEDURES = [
        ("E", "E : Élaboration"),
        ("MEC", "MEC : Mise en compatibilité"),
        ("MAJ", "MAJ : Mise à jour des annexes"),
        ("M", "M : Modification"),
        ("MS", "MS : Modification simplifiée"),
        ("R", "R : Révision"),
        ("RA", "RA : Révision allégée"),
        ("RS", "RS : Révision simplifiée"),
        ("A", "A : Abrogation"),
    ]

    ETATS_NOUVEAU_PLU = [
        ("01", "01 : En cours de procédure"),
        ("02", "02 : Arrêté"),
        ("03", "03 : Opposable"),
        ("07", "07 : Approuvé"),
    ]

    ETATS_ANCIEN_PLU = [
        ("04", "04 : Annulé"),
        ("05", "05 : Remplacé"),
        ("06", "06 : Abrogé"),
        ("08", "08 : Partiellement annulé"),
        ("09", "09 : Caduc"),
    ]

    REFERENTIELS = [
        ("01", "01 (PCI) : Plan cadastral informatisé"),
        ("02", "02 (BD Parcellaire) : BD Parcellaire"),
        ("03", "03 (RPCU) : Représentation parcellaire cadastrale unique"),
        ("04", "04 : Référentiel local"),
        ("05", "05 : Orthophoto et cadastre"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MAJ PLU CNIG")
        self.resize(900, 650)
        self._build_ui()
        self.refresh_layer_combos()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        general_group = QGroupBox("Informations générales de mise à jour du PLU")
        form = QFormLayout(general_group)

        self.procedure_combo = self._make_combo(self.PROCEDURES)
        form.addRow("Type de procédure", self.procedure_combo)

        self.date_appro = self._make_date_edit()
        form.addRow("Date d'approbation du nouveau PLU", self.date_appro)

        self.date_ref = self._make_date_edit()
        form.addRow("Date d'actualité / mise à jour du référentiel cadastral", self.date_ref)

        self.etat_nouveau_combo = self._make_combo(self.ETATS_NOUVEAU_PLU)
        form.addRow("État du nouveau PLU", self.etat_nouveau_combo)

        self.etat_ancien_combo = self._make_combo(self.ETATS_ANCIEN_PLU)
        form.addRow("État de l'ancien PLU", self.etat_ancien_combo)

        self.referentiel_combo = self._make_combo(self.REFERENTIELS)
        form.addRow("Référentiel cadastral utilisé", self.referentiel_combo)

        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText("Sélectionner le dossier de sortie")
        browse_output_btn = QPushButton("Parcourir...")
        browse_output_btn.clicked.connect(self._browse_output_folder)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_folder)
        output_layout.addWidget(browse_output_btn)
        form.addRow("Dossier de sortie", output_layout)

        main_layout.addWidget(general_group)

        layers_group = QGroupBox("Couches à modifier")
        layers_form = QFormLayout(layers_group)

        self.doc_urba_combo, self.doc_urba_path = self._make_layer_selector("DOC_URBA .dbf")
        self.doc_urba_com_combo, self.doc_urba_com_path = self._make_layer_selector("DOC_URBA_COM .dbf")
        self.zone_urba_combo, self.zone_urba_path = self._make_layer_selector("ZONE_URBA .shp")
        self.prescription_surf_combo, self.prescription_surf_path = self._make_layer_selector("PRESCRIPTION_SURF .shp")
        self.prescription_lin_combo, self.prescription_lin_path = self._make_layer_selector("PRESCRIPTION_LIN .shp")
        self.prescription_pct_combo, self.prescription_pct_path = self._make_layer_selector("PRESCRIPTION_PCT .shp")
        self.info_surf_combo, self.info_surf_path = self._make_layer_selector("INFO_SURF .shp")
        self.info_lin_combo, self.info_lin_path = self._make_layer_selector("INFO_LIN .shp")

        layers_form.addRow("DOC_URBA (obligatoire)", self._selector_layout(self.doc_urba_combo, self.doc_urba_path, "DBF (*.dbf)", self._browse_doc_urba))
        layers_form.addRow("DOC_URBA_COM (obligatoire)", self._selector_layout(self.doc_urba_com_combo, self.doc_urba_com_path, "DBF (*.dbf)", self._browse_doc_urba_com))
        layers_form.addRow("ZONE_URBA (optionnel)", self._selector_layout(self.zone_urba_combo, self.zone_urba_path, "SHP (*.shp)", self._browse_zone_urba))
        layers_form.addRow("PRESCRIPTION_SURF (optionnel)", self._selector_layout(self.prescription_surf_combo, self.prescription_surf_path, "SHP (*.shp)", self._browse_prescription_surf))
        layers_form.addRow("PRESCRIPTION_LIN (optionnel)", self._selector_layout(self.prescription_lin_combo, self.prescription_lin_path, "SHP (*.shp)", self._browse_prescription_lin))
        layers_form.addRow("PRESCRIPTION_PCT (optionnel)", self._selector_layout(self.prescription_pct_combo, self.prescription_pct_path, "SHP (*.shp)", self._browse_prescription_pct))
        layers_form.addRow("INFO_SURF (optionnel)", self._selector_layout(self.info_surf_combo, self.info_surf_path, "SHP (*.shp)", self._browse_info_surf))
        layers_form.addRow("INFO_LIN (optionnel)", self._selector_layout(self.info_lin_combo, self.info_lin_path, "SHP (*.shp)", self._browse_info_lin))

        main_layout.addWidget(layers_group)

        info = QLabel(
            "DOC_URBA et DOC_URBA_COM sont obligatoires. Les autres couches sont traitées uniquement si une source est sélectionnée."
        )
        main_layout.addWidget(info)

        buttons = QDialogButtonBox()
        self.execute_button = buttons.addButton("Exécuter", QDialogButtonBox.ButtonRole.AcceptRole)
        self.close_button = buttons.addButton("Fermer", QDialogButtonBox.ButtonRole.RejectRole)
        self.close_button.clicked.connect(self.reject)
        main_layout.addWidget(buttons)

    def _make_combo(self, values):
        combo = QComboBox()
        for code, label in values:
            combo.addItem(label, code)
        return combo

    def _make_date_edit(self):
        widget = QDateEdit()
        widget.setCalendarPopup(True)
        widget.setDisplayFormat("dd/MM/yyyy")
        widget.setDate(QDate.currentDate())
        return widget

    def _make_layer_selector(self, placeholder):
        combo = QComboBox()
        path = QLineEdit()
        path.setPlaceholderText(f"Ou parcourir un fichier {placeholder}")
        return combo, path

    def _selector_layout(self, combo, path_widget, file_filter, browse_slot):
        layout = QHBoxLayout()
        browse_btn = QPushButton("Parcourir...")
        browse_btn.clicked.connect(browse_slot)
        layout.addWidget(combo, 2)
        layout.addWidget(path_widget, 3)
        layout.addWidget(browse_btn)
        return layout

    def refresh_layer_combos(self):
        combos = [
            self.doc_urba_combo,
            self.doc_urba_com_combo,
            self.zone_urba_combo,
            self.prescription_surf_combo,
            self.prescription_lin_combo,
            self.prescription_pct_combo,
            self.info_surf_combo,
            self.info_lin_combo,
        ]
        for combo in combos:
            current = combo.currentData()
            combo.clear()
            combo.addItem("-- Aucune couche du projet --", None)
            for layer in QgsProject.instance().mapLayers().values():
                if layer.type() == QgsMapLayer.LayerType.VectorLayer:
                    combo.addItem(layer.name(), layer.id())
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)


    def _browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier de sortie", self.output_folder.text() or "")
        if folder:
            self.output_folder.setText(folder)

    def _browse_file(self, title, file_filter, path_widget):
        path, _ = QFileDialog.getOpenFileName(self, title, "", f"{file_filter};;Tous les fichiers (*.*)")
        if path:
            path_widget.setText(path)
            if not self.output_folder.text():
                self.output_folder.setText(os.path.dirname(path))

    def _browse_doc_urba(self):
        self._browse_file("Sélectionner le fichier DOC_URBA", "DBF (*.dbf)", self.doc_urba_path)

    def _browse_doc_urba_com(self):
        self._browse_file("Sélectionner le fichier DOC_URBA_COM", "DBF (*.dbf)", self.doc_urba_com_path)

    def _browse_zone_urba(self):
        self._browse_file("Sélectionner le fichier ZONE_URBA", "SHP (*.shp)", self.zone_urba_path)

    def _browse_prescription_surf(self):
        self._browse_file("Sélectionner le fichier PRESCRIPTION_SURF", "SHP (*.shp)", self.prescription_surf_path)

    def _browse_prescription_lin(self):
        self._browse_file("Sélectionner le fichier PRESCRIPTION_LIN", "SHP (*.shp)", self.prescription_lin_path)

    def _browse_prescription_pct(self):
        self._browse_file("Sélectionner le fichier PRESCRIPTION_PCT", "SHP (*.shp)", self.prescription_pct_path)

    def _browse_info_surf(self):
        self._browse_file("Sélectionner le fichier INFO_SURF", "SHP (*.shp)", self.info_surf_path)

    def _browse_info_lin(self):
        self._browse_file("Sélectionner le fichier INFO_LIN", "SHP (*.shp)", self.info_lin_path)

    def values(self):
        return {
            "procedure_code": self.procedure_combo.currentData(),
            "date_appro": self.date_appro.date().toString("yyyyMMdd"),
            "date_ref": self.date_ref.date().toString("yyyyMMdd"),
            "etat_nouveau_code": self.etat_nouveau_combo.currentData(),
            "etat_ancien_code": self.etat_ancien_combo.currentData(),
            "referentiel_code": self.referentiel_combo.currentData(),
            "output_folder": self.output_folder.text().strip(),
            "doc_urba_layer_id": self.doc_urba_combo.currentData(),
            "doc_urba_path": self.doc_urba_path.text().strip(),
            "doc_urba_com_layer_id": self.doc_urba_com_combo.currentData(),
            "doc_urba_com_path": self.doc_urba_com_path.text().strip(),
            "zone_urba_layer_id": self.zone_urba_combo.currentData(),
            "zone_urba_path": self.zone_urba_path.text().strip(),
            "prescription_surf_layer_id": self.prescription_surf_combo.currentData(),
            "prescription_surf_path": self.prescription_surf_path.text().strip(),
            "prescription_lin_layer_id": self.prescription_lin_combo.currentData(),
            "prescription_lin_path": self.prescription_lin_path.text().strip(),
            "prescription_pct_layer_id": self.prescription_pct_combo.currentData(),
            "prescription_pct_path": self.prescription_pct_path.text().strip(),
            "info_surf_layer_id": self.info_surf_combo.currentData(),
            "info_surf_path": self.info_surf_path.text().strip(),
            "info_lin_layer_id": self.info_lin_combo.currentData(),
            "info_lin_path": self.info_lin_path.text().strip(),
        }
