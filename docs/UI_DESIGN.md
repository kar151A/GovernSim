# GovernSim console design

The UI follows a compact enterprise console structure: slate utility header, grouped navigation, white workspace surfaces, blue links, amber primary actions and semantic governance states. The dark appearance uses the same hierarchy with navy surfaces and brighter foregrounds.

- The header appearance button switches light and dark themes. The sign-in page has the same switch.
- The first visit follows the operating-system preference; a deliberate choice is saved locally as `governsim.theme.v1`. Access tokens remain in memory and are not persisted.
- All seven workspaces, forms, inspectors, graphs, feedback and export actions support both appearances.
- Tab groups support Left/Right, Home and End, with labeled panels and visible focus.
- Small screens use a drawer, stacked panels and horizontally scrollable tables.
- Production UI requests still use the original FastAPI endpoints. Backend policy and authorization logic are unchanged.

## Validation

The production TypeScript/Vite build passes. The backend regression suite passes 46 tests with one PostgreSQL test skipped because no disposable PostgreSQL service is available. Desktop screens, capture dialogs, simulation results, tab keyboard navigation, dark appearance and a 390px iframe viewport were inspected with the built frontend and recorded responses from the actual synthetic seed API. This visual harness is outside the repository and is not shipped as application behavior. The managed live preview cannot load Python dependencies, so live browser-to-API verification remains unconfirmed.

## Local update

After applying the source update, run `npm.cmd run build --prefix frontend`, restart the existing FastAPI command and refresh the browser. No dependency changes or database migrations are required.
