# MAJ PLU CNIG

Plugin QGIS permettant d'automatiser la mise à jour des données d'un Plan Local d'Urbanisme (PLU) selon le standard **CNIG PLU v2025-06**.

> ⚠️ **Version expérimentale**  
> Cette première version est en cours de validation et peut encore évoluer.

## Fonctionnalités

Le plugin permet de mettre à jour les données d'un PLU existant à partir des couches et tables sélectionnées par l'utilisateur.

Il prend actuellement en charge :

- `DOC_URBA`
- `DOC_URBA_COM`
- `ZONE_URBA`
- `PRESCRIPTION_SURF`
- `PRESCRIPTION_LIN`
- `PRESCRIPTION_PCT`
- `INFO_SURF`
- `INFO_LIN`

Le plugin permet notamment :

- la mise à jour des identifiants `IDURBA` ;
- la mise à jour des dates liées à la procédure ;
- la gestion des informations relatives à la procédure d'urbanisme ;
- la mise à jour des références aux documents associés ;
- la création des fichiers correspondant à la nouvelle version du PLU ;
- le regroupement automatique des couches produites dans un groupe `NOUVEAU_PLU` dans QGIS.

## Limites de la version actuelle

Cette version est conçue pour le standard **CNIG PLU v2025-06**.

Dans cette première version, seuls les champs obligatoires nécessaires au traitement sont créés lorsqu'ils sont absents.

Il est recommandé de travailler sur une copie des données et de vérifier les fichiers produits avant leur utilisation ou leur diffusion.

## Compatibilité

- QGIS : **3.44 ou version ultérieure**
- Standard : **CNIG PLU v2025-06**

## Installation

Le plugin est destiné à être distribué depuis le dépôt officiel des extensions QGIS.

Pendant la phase de test, il peut également être installé manuellement depuis une archive ZIP via :

`Extensions > Installer/Gérer les extensions > Installer depuis un ZIP`

## Licence

Ce projet est distribué sous licence **GNU General Public License v2.0 (GPL-2.0)**.

## Auteur

**Dalila AMIAR MEFTAH (GEOMA-SIG)**
