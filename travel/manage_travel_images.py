#!/usr/bin/env python3
"""Open a local GUI for editing travel location image galleries."""

from __future__ import annotations

import json
import math
import mimetypes
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


TRAVEL_DIR = Path(__file__).resolve().parent
DATA_FILE = TRAVEL_DIR / "travel-data.js"
IMAGES_DIR = TRAVEL_DIR / "travel_pics"
MAX_IMAGE_SIZE = 25 * 1024 * 1024
IMAGE_EXTENSIONS = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


PAGE = r"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Travel Image Manager</title>
    <style>
        :root {
            color-scheme: light;
            --ink: #17211f;
            --muted: #687470;
            --line: #dce3df;
            --paper: #f4f6f3;
            --panel: #fff;
            --green: #176b55;
            --green-dark: #10513f;
            --red: #a33c38;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background: var(--paper);
            color: var(--ink);
            font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        button, input { font: inherit; }
        button { cursor: pointer; }
        .topbar {
            min-height: 76px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            padding: 14px 28px;
            background: #173c33;
            color: #f5f7f2;
        }
        .brand { display: flex; align-items: center; gap: 13px; }
        .brand-mark {
            width: 38px;
            height: 38px;
            display: grid;
            place-items: center;
            border: 1px solid #8db9a7;
            color: #d9f0e3;
            font-size: 19px;
        }
        h1 { margin: 0; font-size: 17px; font-weight: 650; }
        .subhead { margin-top: 2px; color: #c0d0c7; font-size: 12px; }
        .save-button, .primary-button {
            min-height: 40px;
            padding: 0 16px;
            border: 1px solid transparent;
            background: var(--green);
            color: white;
            font-weight: 650;
        }
        .save-button { background: #e1f1e7; color: #174a38; }
        .save-button:hover { background: white; }
        .save-button:disabled { cursor: default; opacity: .55; }
        .workspace {
            width: min(1200px, 100%);
            min-height: calc(100vh - 76px);
            margin: 0 auto;
            display: grid;
            grid-template-columns: 330px minmax(0, 1fr);
            background: var(--panel);
            border-inline: 1px solid var(--line);
        }
        aside { padding: 24px 18px; border-right: 1px solid var(--line); }
        main { min-width: 0; padding: 28px 34px 40px; }
        .section-title {
            margin: 0 0 14px;
            font-size: 11px;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
            color: var(--muted);
        }
        .sidebar-heading {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }
        .sidebar-heading .section-title { margin-bottom: 14px; }
        .add-location-button {
            min-height: 32px;
            margin: -5px 0 9px;
            padding: 0 9px;
            border: 1px solid var(--line);
            background: white;
            color: var(--green-dark);
            font-size: 12px;
            font-weight: 650;
            white-space: nowrap;
        }
        .add-location-button:hover { background: #edf5ef; }
        dialog {
            width: min(560px, calc(100% - 28px));
            max-height: calc(100dvh - 32px);
            padding: 0;
            border: 1px solid var(--line);
            color: var(--ink);
        }
        dialog::backdrop { background: rgb(14 29 24 / 55%); }
        .dialog-content { padding: 24px; }
        .dialog-content h2 { margin-bottom: 5px; font-size: 21px; }
        .dialog-description { margin: 0 0 20px; color: var(--muted); font-size: 13px; }
        .location-form { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .form-field { display: grid; gap: 5px; min-width: 0; }
        .form-field.full-width { grid-column: 1 / -1; }
        .form-field label { font-size: 12px; font-weight: 650; }
        .form-field input, .form-field select {
            width: 100%;
            min-height: 40px;
            padding: 7px 9px;
            border: 1px solid var(--line);
            border-radius: 2px;
            background: white;
            color: var(--ink);
        }
        .form-field input[type="color"] { padding: 3px; }
        .form-hint { color: var(--muted); font-size: 11px; }
        .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; }
        .dialog-actions button { min-height: 40px; padding-inline: 14px; }
        .search {
            width: 100%;
            height: 40px;
            margin-bottom: 14px;
            padding: 0 11px;
            border: 1px solid var(--line);
            border-radius: 3px;
            outline-color: var(--green);
        }
        .location-list { display: grid; gap: 3px; }
        .location-choice {
            width: 100%;
            padding: 10px 11px;
            border: 0;
            border-left: 3px solid transparent;
            background: transparent;
            color: var(--ink);
            text-align: left;
        }
        .location-choice:hover { background: #f4f7f4; }
        .location-choice.active {
            border-left-color: var(--green);
            background: #eaf3ed;
        }
        .location-name { display: block; font-weight: 650; }
        .location-context { display: block; margin-top: 2px; color: var(--muted); font-size: 12px; }
        .empty-list { padding: 12px; color: var(--muted); font-size: 13px; }
        .detail-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--line);
        }
        h2 { margin: 0; font-size: 24px; line-height: 1.2; font-weight: 700; }
        .location-meta { margin-top: 6px; color: var(--muted); font-size: 13px; }
        .actions { display: flex; gap: 8px; flex-shrink: 0; }
        .primary-button:hover { background: var(--green-dark); }
        .secondary-button, .move-button, .remove-button {
            min-height: 36px;
            padding: 0 11px;
            border: 1px solid var(--line);
            background: white;
            color: var(--ink);
        }
        .secondary-button:hover, .move-button:hover { background: #f2f5f2; }
        .remove-button { color: var(--red); }
        .remove-button:hover { background: #fbefed; }
        button:disabled { cursor: default; opacity: .4; }
        .image-list { display: grid; gap: 10px; padding-top: 16px; }
        .image-row {
            display: grid;
            grid-template-columns: 88px minmax(0, 1fr) auto;
            align-items: center;
            gap: 14px;
            min-height: 94px;
            padding: 8px;
            border: 1px solid var(--line);
            background: white;
        }
        .preview {
            width: 88px;
            height: 74px;
            object-fit: cover;
            background: #edf1ee;
        }
        .image-name { overflow-wrap: anywhere; font-weight: 600; font-size: 13px; }
        .image-path { margin-top: 3px; color: var(--muted); font-size: 11px; }
        .image-controls { display: flex; gap: 5px; }
        .move-button, .remove-button { min-width: 36px; padding: 0 8px; }
        .empty-images {
            margin-top: 18px;
            padding: 38px 20px;
            border: 1px dashed #bdc9c2;
            color: var(--muted);
            text-align: center;
        }
        .empty-images strong { display: block; margin-bottom: 4px; color: var(--ink); }
        .status { min-height: 22px; margin-top: 14px; color: var(--muted); font-size: 13px; }
        .status.error { color: var(--red); }
        .count { color: var(--muted); font-size: 12px; font-weight: 500; letter-spacing: 0; }
        @media (max-width: 720px) {
            .topbar { padding: 12px 16px; }
            .workspace { display: block; border: 0; }
            aside { padding: 18px 16px; border-right: 0; border-bottom: 1px solid var(--line); }
            .location-list { grid-template-columns: repeat(2, minmax(0, 1fr)); max-height: 230px; overflow: auto; }
            main { padding: 22px 16px 32px; }
            .detail-head { display: block; }
            .actions { margin-top: 16px; }
            .image-row { grid-template-columns: 68px minmax(0, 1fr); gap: 10px; }
            .preview { width: 68px; height: 62px; }
            .image-controls { grid-column: 2; }
            .topbar .subhead { display: none; }
            .dialog-content { padding: 20px 16px; }
            .location-form { grid-template-columns: 1fr; }
            .form-field.full-width { grid-column: auto; }
        }
    </style>
</head>
<body>
    <header class="topbar">
        <div class="brand">
            <div class="brand-mark" aria-hidden="true">↗</div>
            <div><h1>Travel Image Manager</h1><div class="subhead">Manage location galleries</div></div>
        </div>
        <button id="save" class="save-button" disabled>Save changes</button>
    </header>
    <div class="workspace">
        <aside>
            <div class="sidebar-heading">
                <h2 class="section-title">Locations <span id="location-count" class="count"></span></h2>
                <button id="new-location" class="add-location-button" type="button">+ Add location</button>
            </div>
            <input id="search" class="search" type="search" placeholder="Filter locations" aria-label="Filter locations">
            <nav id="locations" class="location-list" aria-label="Travel locations"></nav>
        </aside>
        <main>
            <div id="detail"></div>
            <div id="images"></div>
            <div id="status" class="status" role="status" aria-live="polite"></div>
        </main>
    </div>
    <dialog id="location-dialog" aria-labelledby="location-dialog-title">
        <form id="location-form" class="dialog-content">
            <h2 id="location-dialog-title">Add a location</h2>
            <p class="dialog-description">Add a map marker and an image gallery entry.</p>
            <div class="location-form">
                <div class="form-field full-width">
                    <label for="new-location-name">Location</label>
                    <input id="new-location-name" name="location" type="text" maxlength="120" required autofocus>
                </div>
                <div class="form-field full-width">
                    <label for="new-location-title">Display title <span class="count">(optional)</span></label>
                    <input id="new-location-title" name="title" type="text" maxlength="120">
                </div>
                <div class="form-field full-width">
                    <label for="new-location-date">Date</label>
                    <input id="new-location-date" name="date" type="text" maxlength="80" placeholder="e.g. October 2026" required>
                </div>
                <div class="form-field">
                    <label for="new-location-lat">Latitude</label>
                    <input id="new-location-lat" name="lat" type="number" min="-90" max="90" step="any" required>
                </div>
                <div class="form-field">
                    <label for="new-location-lng">Longitude</label>
                    <input id="new-location-lng" name="lng" type="number" min="-180" max="180" step="any" required>
                </div>
                <div class="form-field">
                    <label for="new-location-tag">Category</label>
                    <select id="new-location-tag" name="tag">
                        <option>Travel</option>
                        <option>Career</option>
                        <option>Education</option>
                        <option>Side Quest</option>
                        <option>Life</option>
                        <option>Adventure</option>
                    </select>
                </div>
                <div class="form-field">
                    <label for="new-location-duration">Duration (months)</label>
                    <input id="new-location-duration" name="durationMonths" type="number" min="1" step="1" value="1" required>
                </div>
                <div class="form-field">
                    <label for="new-location-color">Marker color</label>
                    <input id="new-location-color" name="color" type="color" value="#60a5fa">
                </div>
            </div>
            <div class="dialog-actions">
                <button id="cancel-location" class="secondary-button" type="button">Cancel</button>
                <button class="primary-button" type="submit">Create location</button>
            </div>
        </form>
    </dialog>
    <input id="file-picker" type="file" accept="image/avif,image/bmp,image/gif,image/jpeg,image/png,image/webp" multiple hidden>
    <script>
        const appToken = __APP_TOKEN__;
        const locationsElement = document.getElementById('locations');
        const imageElement = document.getElementById('images');
        const detailElement = document.getElementById('detail');
        const statusElement = document.getElementById('status');
        const saveButton = document.getElementById('save');
        const filePicker = document.getElementById('file-picker');
        const locationDialog = document.getElementById('location-dialog');
        const locationForm = document.getElementById('location-form');
        let travelData = [];
        let selectedEntry = null;
        let isDirty = false;

        function allLocations() {
            const result = [];
            function visit(entries, groupName = '') {
                for (const entry of entries) {
                    if (entry.isGroup) {
                        visit(entry.subEvents || [], entry.title || groupName);
                    } else if (entry.location) {
                        result.push({ entry, groupName });
                    }
                }
            }
            visit(travelData);
            return result;
        }

        function setStatus(message, isError = false) {
            statusElement.textContent = message;
            statusElement.classList.toggle('error', isError);
        }

        function markDirty(message = 'Unsaved changes') {
            isDirty = true;
            saveButton.disabled = false;
            setStatus(message);
        }

        function renderLocations() {
            const locations = allLocations();
            const filter = document.getElementById('search').value.trim().toLowerCase();
            document.getElementById('location-count').textContent = `(${locations.length})`;
            locationsElement.replaceChildren();
            const visible = locations.filter(({ entry, groupName }) =>
                `${entry.title || ''} ${entry.location} ${groupName}`.toLowerCase().includes(filter)
            );
            for (const { entry, groupName } of visible) {
                const button = document.createElement('button');
                button.className = `location-choice${entry === selectedEntry ? ' active' : ''}`;
                button.type = 'button';
                const name = document.createElement('span');
                name.className = 'location-name';
                name.textContent = entry.title || entry.location;
                button.append(name);
                const context = document.createElement('span');
                context.className = 'location-context';
                context.textContent = entry.title ? entry.location : groupName;
                button.append(context);
                button.addEventListener('click', () => {
                    selectedEntry = entry;
                    renderLocations();
                    renderEditor();
                });
                locationsElement.append(button);
            }
            if (!visible.length) {
                const empty = document.createElement('div');
                empty.className = 'empty-list';
                empty.textContent = 'No matching locations.';
                locationsElement.append(empty);
            }
        }

        function renderEditor() {
            if (!selectedEntry) return;
            const images = selectedEntry.images || (selectedEntry.images = []);
            detailElement.replaceChildren();
            const header = document.createElement('div');
            header.className = 'detail-head';
            const titleBlock = document.createElement('div');
            const title = document.createElement('h2');
            title.textContent = selectedEntry.title || selectedEntry.location;
            titleBlock.append(title);
            const meta = document.createElement('div');
            meta.className = 'location-meta';
            meta.textContent = selectedEntry.title ? selectedEntry.location : (selectedEntry.date || '');
            titleBlock.append(meta);
            const actions = document.createElement('div');
            actions.className = 'actions';
            const addButton = document.createElement('button');
            addButton.className = 'primary-button';
            addButton.type = 'button';
            addButton.textContent = 'Add images';
            addButton.addEventListener('click', () => filePicker.click());
            actions.append(addButton);
            header.append(titleBlock, actions);
            detailElement.append(header);

            imageElement.replaceChildren();
            if (!images.length) {
                const empty = document.createElement('div');
                empty.className = 'empty-images';
                const heading = document.createElement('strong');
                heading.textContent = 'No images yet';
                empty.append(heading, document.createTextNode('Add photos to this location to build its gallery.'));
                imageElement.append(empty);
                return;
            }

            const list = document.createElement('div');
            list.className = 'image-list';
            images.forEach((imagePath, index) => {
                const row = document.createElement('div');
                row.className = 'image-row';
                const preview = document.createElement('img');
                preview.className = 'preview';
                preview.alt = '';
                preview.src = `/api/image?path=${encodeURIComponent(imagePath)}`;
                const description = document.createElement('div');
                const name = document.createElement('div');
                name.className = 'image-name';
                name.textContent = imagePath.split('/').pop();
                const path = document.createElement('div');
                path.className = 'image-path';
                path.textContent = imagePath;
                description.append(name, path);
                const controls = document.createElement('div');
                controls.className = 'image-controls';
                const up = document.createElement('button');
                up.className = 'move-button';
                up.type = 'button';
                up.textContent = '↑';
                up.title = 'Move image earlier';
                up.setAttribute('aria-label', `Move ${name.textContent} earlier`);
                up.disabled = index === 0;
                up.addEventListener('click', () => moveImage(index, -1));
                const down = document.createElement('button');
                down.className = 'move-button';
                down.type = 'button';
                down.textContent = '↓';
                down.title = 'Move image later';
                down.setAttribute('aria-label', `Move ${name.textContent} later`);
                down.disabled = index === images.length - 1;
                down.addEventListener('click', () => moveImage(index, 1));
                const remove = document.createElement('button');
                remove.className = 'remove-button';
                remove.type = 'button';
                remove.textContent = 'Remove';
                remove.addEventListener('click', () => removeImage(index));
                controls.append(up, down, remove);
                row.append(preview, description, controls);
                list.append(row);
            });
            imageElement.append(list);
        }

        function moveImage(index, offset) {
            const images = selectedEntry.images;
            const target = index + offset;
            if (target < 0 || target >= images.length) return;
            [images[index], images[target]] = [images[target], images[index]];
            markDirty('Image order changed.');
            renderEditor();
        }

        function removeImage(index) {
            selectedEntry.images.splice(index, 1);
            markDirty('Image removed from this gallery. The image file was kept.');
            renderEditor();
        }

        function createLocation(event) {
            event.preventDefault();
            const values = new FormData(locationForm);
            const entry = {
                location: values.get('location').trim(),
                date: values.get('date').trim(),
                lat: Number(values.get('lat')),
                lng: Number(values.get('lng')),
                images: [],
                color: values.get('color'),
                tag: values.get('tag'),
                durationMonths: Number(values.get('durationMonths'))
            };
            const title = values.get('title').trim();
            if (title) entry.title = title;

            travelData.unshift(entry);
            selectedEntry = entry;
            locationForm.reset();
            locationDialog.close();
            markDirty('Location added. Add photos now or save your changes.');
            renderLocations();
            renderEditor();
        }

        async function addFiles(files) {
            if (!selectedEntry || !files.length) return;
            setStatus(`Adding ${files.length} image${files.length === 1 ? '' : 's'}...`);
            try {
                for (const file of files) {
                    const response = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/octet-stream', 'X-App-Token': appToken },
                        body: file
                    });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || 'Image upload failed.');
                    selectedEntry.images ||= [];
                    selectedEntry.images.push(result.path);
                }
                markDirty(`${files.length} image${files.length === 1 ? '' : 's'} added.`);
                renderEditor();
            } catch (error) {
                markDirty('Some changes may need saving.');
                setStatus(error.message, true);
                renderEditor();
            } finally {
                filePicker.value = '';
            }
        }

        async function saveData() {
            saveButton.disabled = true;
            setStatus('Saving travel-data.js...');
            try {
                const response = await fetch('/api/data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-App-Token': appToken },
                    body: JSON.stringify(travelData)
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Could not save travel data.');
                isDirty = false;
                setStatus('Saved travel-data.js.');
            } catch (error) {
                saveButton.disabled = false;
                setStatus(error.message, true);
            }
        }

        document.getElementById('search').addEventListener('input', renderLocations);
        document.getElementById('new-location').addEventListener('click', () => locationDialog.showModal());
        document.getElementById('cancel-location').addEventListener('click', () => locationDialog.close());
        locationForm.addEventListener('submit', createLocation);
        filePicker.addEventListener('change', () => addFiles([...filePicker.files]));
        saveButton.addEventListener('click', saveData);
        window.addEventListener('beforeunload', event => {
            if (isDirty) {
                event.preventDefault();
                event.returnValue = '';
            }
        });

        async function start() {
            try {
                const response = await fetch('/api/data');
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || 'Could not load travel data.');
                travelData = new Function(`${result.source}\nreturn travelData;`)();
                if (!Array.isArray(travelData)) throw new Error('travelData must be an array.');
                selectedEntry = allLocations()[0]?.entry || null;
                renderLocations();
                if (selectedEntry) renderEditor();
            } catch (error) {
                setStatus(error.message, true);
            }
        }
        start();
    </script>
</body>
</html>
"""


class TravelImageHandler(BaseHTTPRequestHandler):
    server: "TravelImageServer"

    def send_bytes(self, content: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, payload: dict[str, object], status: int = 200) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        request = urlparse(self.path)
        if request.path == "/":
            token = json.dumps(self.server.app_token)
            self.send_bytes(PAGE.replace("__APP_TOKEN__", token).encode("utf-8"), "text/html; charset=utf-8")
            return

        if request.path == "/api/data":
            try:
                source = self.server.data_file.read_text(encoding="utf-8")
            except OSError as error:
                self.send_json({"error": f"Could not read travel-data.js: {error}"}, 500)
                return
            self.send_json({"source": source})
            return

        if request.path == "/api/image":
            relative_path = parse_qs(request.query).get("path", [""])[0]
            image_path = (self.server.travel_dir / relative_path).resolve()
            if self.server.images_dir.resolve() not in image_path.parents or not image_path.is_file():
                self.send_error(404)
                return
            try:
                self.send_bytes(image_path.read_bytes(), mimetypes.guess_type(image_path.name)[0] or "application/octet-stream")
            except OSError:
                self.send_error(404)
            return

        self.send_error(404)

    def do_POST(self) -> None:
        if not secrets.compare_digest(self.headers.get("X-App-Token", ""), self.server.app_token):
            self.send_json({"error": "This request did not come from the open manager window."}, 403)
            return

        request = urlparse(self.path)
        if request.path == "/api/upload":
            self.upload_image(request.query)
        elif request.path == "/api/data":
            self.save_data()
        else:
            self.send_error(404)

    def upload_image(self, query: str) -> None:
        filename = parse_qs(query).get("name", [""])[0].replace("\\", "/").split("/")[-1]
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            self.send_json({"error": "Choose a supported raster image (JPG, PNG, WebP, GIF, BMP, or AVIF)."}, 400)
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > MAX_IMAGE_SIZE:
            self.send_json({"error": "Each image must be smaller than 25 MB."}, 413)
            return

        content = self.rfile.read(size)
        if len(content) != size:
            self.send_json({"error": "The image upload was incomplete."}, 400)
            return

        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).stem).strip(".-_") or "travel-image"
        self.server.images_dir.mkdir(parents=True, exist_ok=True)
        with self.server.file_lock:
            counter = 1
            while True:
                numbered_stem = stem if counter == 1 else f"{stem}-{counter}"
                destination = self.server.images_dir / f"{numbered_stem}{suffix}"
                try:
                    with destination.open("xb") as image_file:
                        image_file.write(content)
                    break
                except FileExistsError:
                    counter += 1
                except OSError as error:
                    self.send_json({"error": f"Could not save image: {error}"}, 500)
                    return

        self.send_json({"path": f"travel_pics/{destination.name}"})

    def save_data(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 10 * 1024 * 1024:
                raise ValueError("The travel data payload is empty or too large.")
            entries = json.loads(self.rfile.read(size))
            if not isinstance(entries, list):
                raise ValueError("Travel data must be a list.")
            self.validate_entries(entries)
            source = "const travelData = " + json.dumps(entries, ensure_ascii=False, indent=4) + ";\n"
            temporary_file = self.server.data_file.with_suffix(".js.tmp")
            with self.server.file_lock:
                temporary_file.write_text(source, encoding="utf-8")
                temporary_file.replace(self.server.data_file)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            self.send_json({"error": f"Could not save travel data: {error}"}, 400)
            return
        self.send_json({"saved": True})

    @classmethod
    def validate_entries(cls, entries: list[object]) -> None:
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Every travel entry must be an object.")
            images = entry.get("images", [])
            if not isinstance(images, list) or not all(isinstance(path, str) for path in images):
                raise ValueError("Each entry's images must be a list of file paths.")
            sub_events = entry.get("subEvents", [])
            if not isinstance(sub_events, list):
                raise ValueError("Grouped entry subEvents must be a list.")
            if not entry.get("isGroup"):
                location = entry.get("location")
                if not isinstance(location, str) or not location.strip():
                    raise ValueError("Each location must have a name.")
                for coordinate, lower_bound, upper_bound in (("lat", -90, 90), ("lng", -180, 180)):
                    value = entry.get(coordinate)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or not lower_bound <= value <= upper_bound
                    ):
                        raise ValueError(f"Each location needs a valid {coordinate} coordinate.")
            cls.validate_entries(sub_events)

    def log_message(self, format: str, *args: object) -> None:
        pass


class TravelImageServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], travel_dir: Path, app_token: str):
        super().__init__(address, TravelImageHandler)
        self.travel_dir = travel_dir
        self.data_file = travel_dir / "travel-data.js"
        self.images_dir = travel_dir / "travel_pics"
        self.app_token = app_token
        self.file_lock = threading.Lock()


def main() -> None:
    if not DATA_FILE.is_file():
        raise SystemExit(f"Could not find {DATA_FILE}")

    server = TravelImageServer(("127.0.0.1", 0), TRAVEL_DIR, secrets.token_urlsafe(24))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Travel image manager: {url}", flush=True)
    print("Keep this window open while using the manager. Press Ctrl+C to stop it.", flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTravel image manager stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()