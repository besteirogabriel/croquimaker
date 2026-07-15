# CroquiMaker Editor

React/TypeScript editor for the `CroquiGraph` flow.

## Run

Backend:

```bash
.venv/bin/python -c "from croqui_engine.app.web import app; app.run(host='127.0.0.1', port=5002, debug=False)"
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

Default local login:

- `admin@jobel.local`
- `Jobel@2026!`

## yFiles

`src/diagram/yfiles/YFilesDiagramEngine.ts` is the yFiles integration boundary. The repository does not vendor yFiles because it requires a commercial license.

After installing yFiles, implement this class with:

- `GraphComponent`
- `HierarchicLayout` or `OrthogonalLayout`
- `OrthogonalEdgeRouter`
- automatic label placement
- SVG export from the yFiles graph

Without yFiles, the app uses `FallbackSvgDiagramEngine`, which renders/edit/exports SVG and tries ELK.js for layout.
