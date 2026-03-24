import {
  createContext,
  useCallback,
  useContext,
  useState,
  ReactNode,
} from "react";

type SnackbarType = "success" | "error" | "info" | "warning";

interface SnackbarOptions {
  type?: SnackbarType;
  duration?: number;
}

interface SnackbarState {
  open: boolean;
  message: string;
  type: SnackbarType;
}

interface SnackbarContextValue {
  showSnackbar: (message: string, options?: SnackbarOptions) => void;
  hideSnackbar: () => void;
  snackbar: SnackbarState | null;
}

const SnackbarContext = createContext<SnackbarContextValue | undefined>(
  undefined
);

export const SnackbarProvider = ({ children }: { children: ReactNode }) => {
  const [snackbar, setSnackbar] = useState<SnackbarState | null>(null);

  const hideSnackbar = useCallback(() => {
    setSnackbar((prev) => (prev ? { ...prev, open: false } : null));
  }, []);

  const showSnackbar = useCallback(
    (message: string, options?: SnackbarOptions) => {
      const duration = options?.duration ?? 4000;
      const type = options?.type ?? "info";

      setSnackbar({ open: true, message, type });

      if (duration > 0) {
        window.setTimeout(() => {
          hideSnackbar();
        }, duration);
      }
    },
    [hideSnackbar]
  );

  return (
    <SnackbarContext.Provider value={{ showSnackbar, hideSnackbar, snackbar }}>
      {children}
      {snackbar && snackbar.open && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50">
          <div
            className={`px-4 py-3 rounded-lg shadow-lg text-sm text-white ${
              snackbar.type === "success"
                ? "bg-emerald-600"
                : snackbar.type === "error"
                ? "bg-red-600"
                : snackbar.type === "warning"
                ? "bg-amber-500"
                : "bg-slate-800"
            }`}
          >
            {snackbar.message}
          </div>
        </div>
      )}
    </SnackbarContext.Provider>
  );
};

export const useSnackbar = (): SnackbarContextValue => {
  const ctx = useContext(SnackbarContext);
  if (!ctx) {
    throw new Error("useSnackbar must be used within a SnackbarProvider");
  }
  return ctx;
};
