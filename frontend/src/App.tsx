import { RouterProvider } from "react-router-dom";

import { useAuthBootstrap } from "./hooks/useAuthBootstrap";
import { router } from "./router";

function App() {
  useAuthBootstrap();
  return <RouterProvider router={router} />;
}

export default App;
