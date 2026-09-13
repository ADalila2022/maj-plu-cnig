# -*- coding: utf-8 -*-

import os
import re
import shutil

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QInputDialog, QLineEdit
from qgis.core import QgsFeature, QgsField, QgsProject, QgsVectorLayer

from .maj_plu_cnig_dialog import MajPluCnigDialog


class MajPluCnigPlugin:
    """Plugin QGIS de pour la mise à jour CNIG PLU."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        self.action = QAction(QIcon(icon_path), "MAJ PLU CNIG", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("MAJ PLU CNIG", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("MAJ PLU CNIG", self.action)
            self.iface.removeToolBarIcon(self.action)

    def run(self):
        self.dialog = MajPluCnigDialog(self.iface.mainWindow())
        self.dialog.execute_button.clicked.connect(self._execute_from_dialog)
        self.dialog.show()

    def _execute_from_dialog(self):
        values = self.dialog.values()
        try:
            outputs = self.process_all(**values)
            loaded_names = self._load_outputs_to_group(outputs)
            QMessageBox.information(
                self.dialog,
                "Traitement terminé",
                "Fichiers créés et ajoutés au groupe NOUVEAU_PLU :\n"
                + "\n".join(outputs),
            )
        except Exception as exc:
            QMessageBox.critical(self.dialog, "Erreur", str(exc))

    def _load_outputs_to_group(self, output_paths):
        """Ajoute les fichiers de sortie dans un groupe NOUVEAU_PLU du panneau des couches."""
        project = QgsProject.instance()
        root = project.layerTreeRoot()
        group_name = "NOUVEAU_PLU"

        group = root.findGroup(group_name)
        if group is None:
            group = root.addGroup(group_name)

        loaded_names = []
        for path in output_paths:
            normalized_path = os.path.abspath(os.path.normpath(path))
            layer_name = os.path.splitext(os.path.basename(normalized_path))[0]
            layer = QgsVectorLayer(normalized_path, layer_name, "ogr")
            if not layer.isValid():
                raise ValueError(f"Le fichier a été créé mais n'a pas pu être ajouté au panneau des couches : {normalized_path}")

            project.addMapLayer(layer, False)
            group.addLayer(layer)
            loaded_names.append(layer_name)

        group.setExpanded(True)
        return loaded_names

    def process_all(
        self,
        procedure_code,
        date_appro,
        date_ref,
        etat_nouveau_code,
        etat_ancien_code,
        referentiel_code,
        output_folder,
        doc_urba_layer_id=None,
        doc_urba_path="",
        doc_urba_com_layer_id=None,
        doc_urba_com_path="",
        zone_urba_layer_id=None,
        zone_urba_path="",
        prescription_surf_layer_id=None,
        prescription_surf_path="",
        prescription_lin_layer_id=None,
        prescription_lin_path="",
        prescription_pct_layer_id=None,
        prescription_pct_path="",
        info_surf_layer_id=None,
        info_surf_path="",
        info_lin_layer_id=None,
        info_lin_path="",
    ):
        if not output_folder or not os.path.isdir(output_folder):
            raise ValueError("Veuillez sélectionner un dossier de sortie valide.")

        doc_source = self._resolve_source(doc_urba_layer_id, doc_urba_path)
        if not doc_source:
            raise ValueError("DOC_URBA est obligatoire : sélectionnez une couche du projet ou un fichier DBF.")

        doc_com_source = self._resolve_source(doc_urba_com_layer_id, doc_urba_com_path)
        if not doc_com_source:
            raise ValueError("DOC_URBA_COM est obligatoire : sélectionnez une couche du projet ou un fichier DBF.")

        doc_output, code_commune, new_idurba, nomreg = self._process_doc_urba(
            source_path=doc_source,
            procedure_code=procedure_code,
            date_appro=date_appro,
            date_ref=date_ref,
            etat_nouveau_code=etat_nouveau_code,
            etat_ancien_code=etat_ancien_code,
            referentiel_code=referentiel_code,
            output_folder=output_folder,
        )
        doc_com_output = self._process_doc_urba_com(doc_com_source, output_folder, date_appro, new_idurba)
        outputs = [doc_output, doc_com_output]

        zone_source = self._resolve_source(zone_urba_layer_id, zone_urba_path)
        if zone_source:
            outputs.append(self._process_zone_urba(zone_source, output_folder, date_appro, new_idurba, nomreg))

        prescription_source = self._resolve_source(prescription_surf_layer_id, prescription_surf_path)
        if prescription_source:
            outputs.append(self._process_prescription_surf(prescription_source, output_folder, date_appro, new_idurba, nomreg, code_commune))

        prescription_lin_source = self._resolve_source(prescription_lin_layer_id, prescription_lin_path)
        if prescription_lin_source:
            outputs.append(self._process_prescription_lin(prescription_lin_source, output_folder, date_appro, new_idurba, nomreg, code_commune))

        prescription_pct_source = self._resolve_source(prescription_pct_layer_id, prescription_pct_path)
        if prescription_pct_source:
            outputs.append(self._process_prescription_pct(prescription_pct_source, output_folder, date_appro, new_idurba, nomreg, code_commune))

        info_source = self._resolve_source(info_surf_layer_id, info_surf_path)
        if info_source:
            outputs.append(self._process_info_surf(info_source, output_folder, date_appro, new_idurba))

        info_lin_source = self._resolve_source(info_lin_layer_id, info_lin_path)
        if info_lin_source:
            outputs.append(self._process_info_lin(info_lin_source, output_folder, date_appro, new_idurba))

        return outputs

    def _resolve_source(self, layer_id, browsed_path):
        """Priorité à la couche déjà chargée dans le projet si elle est sélectionnée."""
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                src = layer.source().split("|")[0]
                if src and os.path.exists(src):
                    return os.path.abspath(os.path.normpath(src))
                raise ValueError(f"La couche sélectionnée '{layer.name()}' ne pointe pas vers un fichier local exploitable.")
        return os.path.abspath(os.path.normpath(browsed_path.strip())) if browsed_path else ""

    def _process_doc_urba(
        self,
        source_path,
        procedure_code,
        date_appro,
        date_ref,
        etat_nouveau_code,
        etat_ancien_code,
        referentiel_code,
        output_folder,
    ):
        filename = os.path.basename(source_path)
        match = re.match(r"^(?P<codecom>[^_]+)_DOC_URBA_(?P<olddate>\d{8})\.dbf$", filename, re.IGNORECASE)
        if not match:
            raise ValueError("DOC_URBA doit respecter le format codecommune_DOC_URBA_AAAAMMJJ.dbf")

        code_commune = match.group("codecom")
        old_date = match.group("olddate")
        output_path = os.path.abspath(os.path.normpath(os.path.join(output_folder, filename.replace(old_date, date_appro))))
        self._copy_dataset_family(source_path, output_path)

        layer = self._open_layer(output_path, "DOC_URBA")
        self._ensure_text_field(layer, "NOMRAPP", 80)
        self._ensure_text_field(layer, "URLRAPP", 254)
        layer.updateFields()

        self._require_fields(layer, [
            "ETAT", "DATAPPRO", "DATEFIN", "IDURBA", "TYPEDOC", "NOMPROC",
            "NOMREG", "NOMPLAN", "TYPEREF", "DATEREF",
        ], "DOC_URBA")

        features = list(layer.getFeatures())
        if not features:
            raise ValueError("DOC_URBA ne contient aucune ligne.")

        latest_feature = max(features, key=lambda feat: str(feat["DATAPPRO"] or ""))
        next_nomproc = self._compute_next_nomproc(features, procedure_code)
        new_idurba = self._build_plu_idurba_from_doc_filename(filename, date_appro)
        nomreg = f"{code_commune}_reglement_{date_appro}.pdf"
        nomplan = f"{code_commune}_reglement_graphique_{date_appro}.pdf"
        nomrapp = self._ask_nomrapp_value(code_commune, date_appro)

        self._start_edit(layer)
        try:
            self._change(layer, latest_feature.id(), "ETAT", etat_ancien_code)
            self._change(layer, latest_feature.id(), "DATEFIN", date_appro)

            new_feature = QgsFeature(layer.fields())
            new_feature.setAttributes([None] * len(layer.fields()))
            self._set_attr(new_feature, layer, "IDURBA", new_idurba)
            self._set_attr(new_feature, layer, "TYPEDOC", "PLU")
            self._set_attr(new_feature, layer, "ETAT", etat_nouveau_code)
            self._set_attr(new_feature, layer, "NOMPROC", next_nomproc)
            self._set_attr(new_feature, layer, "DATAPPRO", date_appro)
            self._set_attr(new_feature, layer, "NOMREG", nomreg)
            self._set_attr(new_feature, layer, "NOMPLAN", nomplan)
            self._set_attr(new_feature, layer, "NOMRAPP", nomrapp)
            self._set_attr(new_feature, layer, "TYPEREF", referentiel_code)
            self._set_attr(new_feature, layer, "DATEREF", date_ref)
            if not layer.addFeature(new_feature):
                raise ValueError("Impossible d'ajouter la nouvelle ligne DOC_URBA.")
            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise

        return output_path, code_commune, new_idurba, nomreg

    def _ask_nomrapp_value(self, code_commune, date_appro):
        """Demande la valeur à écrire dans DOC_URBA.NOMRAPP pour la nouvelle ligne."""
        default_value = f"{code_commune}_rapport_{date_appro}.pdf"
        parent = self.dialog if self.dialog is not None else self.iface.mainWindow()

        reply = QMessageBox.question(
            parent,
            "Nom du rapport de présentation - DOC_URBA",
            "Pour la table DOC_URBA, souhaitez-vous utiliser le nom par défaut du rapport de présentation ?\n\n"
            f"{default_value}\n\n"
            "Répondez Non pour saisir un autre nom de fichier.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            return default_value

        custom_value, ok = QInputDialog.getText(
            parent,
            "Nom du rapport de présentation - DOC_URBA",
            "Saisissez le nom du fichier du rapport de présentation à écrire dans NOMRAPP :",
            QLineEdit.Normal,
            default_value,
        )
        if not ok:
            raise ValueError("Traitement annulé : aucun nom de fichier NOMRAPP n'a été validé.")

        custom_value = custom_value.strip()
        if not custom_value:
            raise ValueError("Le nom du fichier du rapport de présentation ne peut pas être vide.")
        return custom_value

    def _process_doc_urba_com(self, source_path, output_folder, date_appro, new_idurba):
        filename = os.path.basename(source_path)
        match = re.match(r"^(?P<codecom>[^_]+)_DOC_URBA_COM_(?P<olddate>\d{8})\.dbf$", filename, re.IGNORECASE)
        if not match:
            raise ValueError("DOC_URBA_COM doit respecter le format codecommune_DOC_URBA_COM_AAAAMMJJ.dbf")

        old_date = match.group("olddate")
        output_path = os.path.abspath(os.path.normpath(os.path.join(output_folder, filename.replace(old_date, date_appro))))
        self._copy_dataset_family(source_path, output_path)

        layer = self._open_layer(output_path, "DOC_URBA_COM")
        self._require_fields(layer, ["IDURBA"], "DOC_URBA_COM")

        self._start_edit(layer)
        try:
            for feat in layer.getFeatures():
                self._change(layer, feat.id(), "IDURBA", new_idurba)
            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise
        return output_path

    def _process_zone_urba(self, source_path, output_folder, date_appro, new_idurba, nomreg):
        filename = os.path.basename(source_path)
        output_path = self._dated_output_path(source_path, output_folder, date_appro, "ZONE_URBA", ".shp")
        self._copy_dataset_family(source_path, output_path)
        layer = self._open_layer(output_path, "ZONE_URBA")

        for field_name, length in [("FORMDOMI", 4), ("DESTOUI", 120), ("DESTCDT", 120), ("DESTNON", 120), ("SYMBOLE", 20)]:
            self._ensure_text_field(layer, field_name, length)
        layer.updateFields()
        self._require_fields(layer, ["IDURBA", "NOMFIC"], "ZONE_URBA")

        self._start_edit(layer)
        try:
            for feat in layer.getFeatures():
                self._change(layer, feat.id(), "IDURBA", new_idurba)
                self._change(layer, feat.id(), "NOMFIC", nomreg)
            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise
        return output_path

    def _process_prescription_surf(self, source_path, output_folder, date_appro, new_idurba, nomreg, code_commune):
        return self._process_prescription_layer(
            source_path=source_path,
            output_folder=output_folder,
            date_appro=date_appro,
            new_idurba=new_idurba,
            nomreg=nomreg,
            code_commune=code_commune,
            expected_token="PRESCRIPTION_SURF",
            layer_name="PRESCRIPTION_SURF",
        )

    def _process_prescription_lin(self, source_path, output_folder, date_appro, new_idurba, nomreg, code_commune):
        return self._process_prescription_layer(
            source_path=source_path,
            output_folder=output_folder,
            date_appro=date_appro,
            new_idurba=new_idurba,
            nomreg=nomreg,
            code_commune=code_commune,
            expected_token="PRESCRIPTION_LIN",
            layer_name="PRESCRIPTION_LIN",
        )

    def _process_prescription_pct(self, source_path, output_folder, date_appro, new_idurba, nomreg, code_commune):
        return self._process_prescription_layer(
            source_path=source_path,
            output_folder=output_folder,
            date_appro=date_appro,
            new_idurba=new_idurba,
            nomreg=nomreg,
            code_commune=code_commune,
            expected_token="PRESCRIPTION_PCT",
            layer_name="PRESCRIPTION_PCT",
        )

    def _process_prescription_layer(self, source_path, output_folder, date_appro, new_idurba, nomreg, code_commune, expected_token, layer_name):
        output_path = self._dated_output_path(source_path, output_folder, date_appro, expected_token, ".shp")
        self._copy_dataset_family(source_path, output_path)
        layer = self._open_layer(output_path, layer_name)

        self._ensure_text_field(layer, "NATURE", 50)
        self._ensure_text_field(layer, "SYMBOLE", 20)
        layer.updateFields()
        self._require_fields(layer, ["IDURBA", "NOMFIC"], layer_name)

        update_choices = {}
        self._start_edit(layer)
        try:
            for feat in layer.getFeatures():
                self._change(layer, feat.id(), "IDURBA", new_idurba)

                nomfic = str(feat["NOMFIC"] or "").strip()
                if not nomfic:
                    continue

                if self._is_reglement_nomfic(nomfic, code_commune):
                    self._change(layer, feat.id(), "NOMFIC", nomreg)
                else:
                    doc_type = self._extract_document_type_from_nomfic(nomfic, code_commune)
                    if doc_type not in update_choices:
                        update_choices[doc_type] = self._ask_update_nomfic_date(layer_name, doc_type, nomfic)
                    if update_choices[doc_type]:
                        self._change(layer, feat.id(), "NOMFIC", self._replace_pdf_date(nomfic, date_appro))

            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise
        return output_path

    def _process_info_surf(self, source_path, output_folder, date_appro, new_idurba):
        output_path = self._dated_output_path(source_path, output_folder, date_appro, "INFO_SURF", ".shp")
        self._copy_dataset_family(source_path, output_path)
        layer = self._open_layer(output_path, "INFO_SURF")

        self._ensure_text_field(layer, "SYMBOLE", 20)
        layer.updateFields()
        # NOMFIC ne doit pas être modifié pour INFO_SURF : les fichiers annexes ne changent pas.
        self._require_fields(layer, ["IDURBA"], "INFO_SURF")

        self._start_edit(layer)
        try:
            for feat in layer.getFeatures():
                self._change(layer, feat.id(), "IDURBA", new_idurba)
            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise
        return output_path


    def _process_info_lin(self, source_path, output_folder, date_appro, new_idurba):
        output_path = self._dated_output_path(source_path, output_folder, date_appro, "INFO_LIN", ".shp")
        self._copy_dataset_family(source_path, output_path)
        layer = self._open_layer(output_path, "INFO_LIN")

        self._ensure_text_field(layer, "SYMBOLE", 20)
        layer.updateFields()
        self._require_fields(layer, ["IDURBA"], "INFO_LIN")

        self._start_edit(layer)
        try:
            for feat in layer.getFeatures():
                self._change(layer, feat.id(), "IDURBA", new_idurba)
            self._commit(layer)
        except Exception:
            layer.rollBack()
            raise
        return output_path

    def _is_reglement_nomfic(self, nomfic, code_commune):
        value = (nomfic or "").strip().lower()
        return value.startswith(f"{code_commune.lower()}_reglement")

    def _extract_document_type_from_nomfic(self, nomfic, code_commune):
        """
        Extrait TypeDocument depuis codecommune_TypeDocument_AAAAMMJJ.pdf.
        Exemple : 45188_orientations_amenagement_20221213.pdf -> orientations_amenagement.
        """
        value = os.path.basename(str(nomfic or "").strip())
        pattern = rf"^{re.escape(code_commune)}_(?P<doctype>.+?)_\d{{8}}\.pdf$"
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            return match.group("doctype")
        return value or "document"

    def _ask_update_nomfic_date(self, layer_name, doc_type, nomfic):
        message = (
            f"Couche concernée : {layer_name}\n\n"
            "Le fichier référencé dans le champ NOMFIC ne correspond pas au règlement :\n\n"
            f"{nomfic}\n\n"
            f"Type de document détecté : {doc_type}\n\n"
            f"Voulez-vous mettre à jour la date du fichier « {doc_type} » pour la couche {layer_name} ?"
        )
        parent = self.dialog if self.dialog is not None else self.iface.mainWindow()
        reply = QMessageBox.question(
            parent,
            f"Mise à jour NOMFIC - {layer_name}",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _copy_dataset_family(self, input_path, output_path):
        if not input_path or not os.path.exists(input_path):
            raise ValueError(f"Fichier introuvable : {input_path}")

        input_path = os.path.abspath(os.path.normpath(input_path))
        output_path = os.path.abspath(os.path.normpath(output_path))
        input_root, _ = os.path.splitext(input_path)
        output_root, _ = os.path.splitext(output_path)

        if input_root.lower() == output_root.lower():
            raise ValueError("Le fichier de sortie est identique au fichier source. Choisissez un dossier de sortie différent ou une nouvelle date d'approbation.")

        if self._dataset_family_exists(output_path):
            if not self._confirm_replace(output_path):
                raise ValueError(f"Traitement annulé : le fichier existe déjà et ne sera pas remplacé : {output_path}")
            self._delete_dataset_family(output_path)

        input_dir = os.path.dirname(input_path)
        input_base = os.path.basename(input_root)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        copied = False
        for name in os.listdir(input_dir):
            root, ext = os.path.splitext(name)
            if root.lower() == input_base.lower():
                src = os.path.join(input_dir, name)
                dst = output_root + ext.lower()
                shutil.copy2(src, dst)
                copied = True
        if not copied:
            shutil.copy2(input_path, output_path)

    def _dataset_family_exists(self, path):
        root, _ = os.path.splitext(os.path.abspath(os.path.normpath(path)))
        folder = os.path.dirname(root)
        base = os.path.basename(root).lower()
        if not os.path.isdir(folder):
            return False
        for name in os.listdir(folder):
            if os.path.splitext(name)[0].lower() == base:
                return True
        return False

    def _delete_dataset_family(self, path):
        root, _ = os.path.splitext(os.path.abspath(os.path.normpath(path)))
        folder = os.path.dirname(root)
        base = os.path.basename(root).lower()
        if not os.path.isdir(folder):
            return
        for name in os.listdir(folder):
            if os.path.splitext(name)[0].lower() == base:
                os.remove(os.path.join(folder, name))

    def _confirm_replace(self, path):
        message = (
            "Le fichier de sortie existe déjà :\n\n"
            f"{os.path.abspath(os.path.normpath(path))}\n\n"
            "Voulez-vous le remplacer ?\n\n"
            "Aucun autre nom de fichier ne sera proposé."
        )
        parent = self.dialog if self.dialog is not None else self.iface.mainWindow()
        reply = QMessageBox.question(parent, "Fichier existant", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes

    def _dated_output_path(self, source_path, output_folder, date_appro, expected_token, expected_ext):
        filename = os.path.basename(source_path)
        pattern = rf"^(?P<codecom>[^_]+)_{expected_token}_(?P<olddate>\d{{8}}){re.escape(expected_ext)}$"
        match = re.match(pattern, filename, re.IGNORECASE)
        if not match:
            raise ValueError(f"{expected_token} doit respecter le format codecommune_{expected_token}_AAAAMMJJ{expected_ext}")
        return os.path.abspath(os.path.normpath(os.path.join(output_folder, filename.replace(match.group("olddate"), date_appro))))

    def _open_layer(self, path, name):
        layer = QgsVectorLayer(path, name, "ogr")
        if not layer.isValid():
            raise ValueError(f"Impossible d'ouvrir {name} avec QGIS/OGR : {path}")
        return layer

    def _ensure_text_field(self, layer, field_name, length):
        if layer.fields().indexFromName(field_name) != -1:
            return
        if not layer.dataProvider().addAttributes([QgsField(field_name, QVariant.String, "string", length)]):
            raise ValueError(f"Impossible de créer le champ {field_name}.")
        layer.updateFields()

    def _require_fields(self, layer, field_names, layer_name):
        missing = [f for f in field_names if layer.fields().indexFromName(f) == -1]
        if missing:
            raise ValueError(f"Champs obligatoires absents dans {layer_name} : " + ", ".join(missing))

    def _start_edit(self, layer):
        if not layer.startEditing():
            raise ValueError(f"Impossible de passer {layer.name()} en mode édition.")

    def _commit(self, layer):
        if not layer.commitChanges():
            errors = "; ".join(layer.commitErrors())
            raise ValueError("Échec de l'enregistrement des modifications : " + errors)

    def _change(self, layer, fid, field_name, value):
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            raise ValueError(f"Champ introuvable : {field_name}")
        if not layer.changeAttributeValue(fid, idx, value):
            raise ValueError(f"Impossible de modifier {field_name}.")

    def _set_attr(self, feature, layer, field_name, value):
        idx = layer.fields().indexFromName(field_name)
        if idx == -1:
            raise ValueError(f"Champ introuvable : {field_name}")
        feature.setAttribute(idx, value)

    def _compute_next_nomproc(self, features, procedure_code):
        pattern = re.compile(rf"^{re.escape(procedure_code)}(\d+)$", re.IGNORECASE)
        max_number = 0
        for feature in features:
            try:
                value = str(feature["NOMPROC"] or "").strip()
            except KeyError:
                value = ""
            match = pattern.match(value)
            if match:
                max_number = max(max_number, int(match.group(1)))
        return f"{procedure_code}{max_number + 1}"

    def _build_plu_idurba_from_doc_filename(self, filename, date_appro):
        """
        Construit l'IDURBA à partir du code commune du fichier DOC_URBA,
        en produisant toujours : codecommune_PLU_AAAAMMJJ.
        Exemple : 78683_DOC_URBA_20220922.dbf -> 78683_PLU_20260207.
        """
        code_commune = filename.split("_", 1)[0]
        return f"{code_commune}_PLU_{date_appro}"

    def _replace_last_date_without_ext(self, filename, date_appro):
        root, _ = os.path.splitext(filename)
        return re.sub(r"\d{8}$", date_appro, root)

    def _replace_pdf_date(self, value, date_appro):
        if not value:
            return value
        new_value = re.sub(r"\d{8}(?=\.pdf$)", date_appro, value, flags=re.IGNORECASE)
        if new_value == value:
            new_value = re.sub(r"\d{8}", date_appro, value)
        return new_value
