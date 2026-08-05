import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface Toast {
  id: number;
  kind: "info" | "success" | "error";
  message: string;
}

interface UIContextValue {
  dark: boolean;
  toggleDark: () => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toasts: Toast[];
  toast: (message: string, kind?: Toast["kind"]) => void;
  dismissToast: (id: number) => void;
}

const THEME_KEY = "sentinel-theme";

const UIContext = createContext<UIContextValue | null>(null);

export function UIProvider({ children }: { children: React.ReactNode }) {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextToastId = useRef(1);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
    } catch {
      /* private mode — theme still applies for the session */
    }
  }, [dark]);

  const toggleDark = useCallback(() => setDark((d) => !d), []);

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    (message: string, kind: Toast["kind"] = "info") => {
      const id = nextToastId.current++;
      setToasts((current) => [...current, { id, kind, message }]);
      window.setTimeout(() => dismissToast(id), 6000);
    },
    [dismissToast],
  );

  const value = useMemo(
    () => ({
      dark,
      toggleDark,
      sidebarOpen,
      setSidebarOpen,
      toasts,
      toast,
      dismissToast,
    }),
    [dark, toggleDark, sidebarOpen, toasts, toast, dismissToast],
  );

  return <UIContext.Provider value={value}>{children}</UIContext.Provider>;
}

export function useUI(): UIContextValue {
  const ctx = useContext(UIContext);
  if (!ctx) throw new Error("useUI must be used within a UIProvider");
  return ctx;
}
