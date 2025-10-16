#  Python Batch Mutation Wizard (PyBmw)

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-brightgreen" alt="Version 1.0"/>
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License: MIT"/>
</p>

PyBmw is an advanced plugin for PyMOL designed to streamline in-silico protein mutagenesis. It provides a powerful graphical user interface (GUI) to perform single and large-scale batch mutations efficiently, enhancing the standard capabilities of PyMOL's mutagenesis wizard.

<p align="center">
  <img width="600" alt="PyBmw Plugin GUI" src="https://github.com/user-attachments/assets/670355d8-74b8-4a5f-8b39-824cbd2e6c64" />
</p>

---

## 📋 Table of Contents
* [🚀 Installation](#installation)
    * [Method 1: URL Installation (Recommended)](#method-1-url-installation-recommended)
    * [Method 2: Manual Installation](#method-2-manual-installation)
* [📖 Documentation](#documentation)
    * [✨ Core Features](#-core-features)
    * [⚙️ Basic Workflow](#️-basic-workflow)
* [✍️ Authors](#️-authors)
* [📄 License](#-license)

---

## 🚀 Installation

PyBmw can be installed using one of the following methods.

### Method 1: URL Installation (Recommended)

This method allows for direct installation into PyMOL from the GitHub repository.

1.  **Copy the Raw File URL**:
    ```
    https://raw.githubusercontent.com/protmind/Python-Batch-Mutation-Wizard-PyBmw-/main/pybmw.py
    ```

2.  **Install via PyMOL Plugin Manager**:
    * Launch PyMOL and navigate to `Plugin` -> `Plugin Manager`.
    * Select the `Install New Plugin` tab, then the `From URL...` sub-tab.
    * Paste the copied URL into the "URL" field and click **Fetch**.
    * The plugin will be installed and available in the `Plugin` menu.

<p align="center">
  <img width="500" alt="PyMOL Plugin Manager URL Install" src="https://github.com/user-attachments/assets/b964f654-52e0-4d03-80f0-46b3dc2b0f4f" />
</p>

### Method 2: Manual Installation

This method involves downloading the script and installing it from a local file.

1.  **Download the Plugin Script**: Download the `pybmw.py` script from this repository via the `Code` -> `Download ZIP` option.
<p align="center">
  <img width="500" alt="Download ZIP from GitHub" src="https://github.com/user-attachments/assets/6edd7a29-ba51-4ffa-82d7-1c5df41c7450" />
</p>

2.  **Install via PyMOL Plugin Manager**:
    * Launch PyMOL and navigate to `Plugin` -> `Plugin Manager`.
    * Select the `Install New Plugin` tab.
    * Click `Choose file...` and locate the `pybmw.py` script on your local machine.
<p align="center">
  <img width="600" alt="Choose File for Plugin Installation" src="https://github.com/user-attachments/assets/bed8ea9a-6c00-498c-9c4b-c3c793ff5ee8" />
</p>

---

## 📖 Documentation

### ✨ Core Features

PyBmw offers several modes of operation to accommodate diverse mutagenesis workflows.

#### 🎯 High-Throughput Mutagenesis
* **Batch Mode**: Apply a single amino acid mutation to a large selection of residues simultaneously. Ideal for creating alanine scanning libraries.
* **Import from CSV**: For extensive mutagenesis projects, define mutations in an external CSV file. This feature automates the selection and staging of hundreds of mutations.
    * **CSV File Format**: A simple two-column file with `Residue Identifier` (`Chain ResidueID`) and `Target Amino Acid` (three-letter code). No header row is needed.
    * **Example (`mutations.csv`)**:
        ```csv
        A 123,TRP
        A 45,ALA
        B 98,PHE
        C 210,GLY
        ```

#### 🔬 Precision and Control
* **Individual Mode**: Assign a unique target mutation to each residue in a selection via an organized table.
* **Step-by-Step Mode**: Sequentially execute a list of mutations, allowing for individual rotamer selection and visual inspection at each step.

#### 🔧 Additional Functionality
* **Smart Refinement**: Utilizes PyMOL's `sculpting` feature to refine sidechain rotamer conformations.
* **Visual Feedback**: Staged residues are highlighted in **yellow**. Mutated residues turn **cyan** and are labeled for easy identification.
* **Data Export**: Save your work as a clean PDB file, a complete PyMOL session file (`.pse`), or both.

---

### ⚙️ Basic Workflow

The following steps outline a typical mutagenesis session using PyBmw.

<p align="center">
  <img width="600" alt="Protein with residues selected" src="https://github.com/user-attachments/assets/b64515a5-b544-4477-b414-d595a3328b8a" />
</p>

1.  **Load Structure**: Open a PDB file in PyMOL.
2.  **Select Residues**: Select one or more residues for mutation in the PyMOL viewer.
3.  **Launch PyBmw**: Navigate to `Plugin` -> `Python Batch Mutation Wizard (PyBmw)`.
4.  **Stage Residues**: Click **Add to Selection** in the plugin window to load the selected residues into the mutation table.
5.  **Configure and Execute Mutations**:
    * Choose the desired mode (**Batch**, **Individual**, **Step-by-Step**, or **Import from CSV**).
    * Define the target mutations.
    * Click **Mutate All** or step through with **Apply This Mutation**.
<p align="center">
  <img width="500" alt="Individual Mode Table" src="https://github.com/user-attachments/assets/4d622c05-fab1-4319-ae88-1d6fda7a3897" />
</p>
6.  **Export Your Work**: Click **Export Files...** to save the modified coordinates and/or session.

---

## ✍️ Authors
* **Jayaraman Muthukumaran**
* **ND Yash**
* **Abhinav Singh**

---

## 📄 License
This project is distributed under the MIT License. See the `LICENSE` file for more information.
