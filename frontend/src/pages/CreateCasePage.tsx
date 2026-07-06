import { Navigate } from "react-router-dom";

export default function CreateCasePage() {
  return <Navigate to="/cases?newCase=true" replace />;
}
