import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, Home } from "lucide-react";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error("404 Error: User attempted to access non-existent route:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-2xl border border-border/80 bg-card/75 p-8 text-center backdrop-blur-2xl sm:p-10">
        <div className="mb-3 text-[10px] uppercase tracking-[0.18em] text-secondary">
          Route not found
        </div>
        <h1 className="font-display text-5xl font-bold text-foreground sm:text-6xl">404</h1>
        <p className="mx-auto mt-4 max-w-xl text-base leading-8 text-muted-foreground">
          There is no route mapped for <span className="text-foreground">{location.pathname}</span>.
          The public landing page and workspace routes are available below.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 border border-secondary/30 bg-secondary/10 px-5 py-3 text-[11px] font-bold uppercase tracking-[0.18em] text-secondary transition-colors hover:bg-secondary/20"
          >
            <Home size={14} />
            Landing page
          </Link>
          <Link
            to="/workspace"
            className="inline-flex items-center justify-center gap-2 border border-border px-5 py-3 text-[11px] uppercase tracking-[0.18em] text-muted-foreground transition-colors hover:border-primary/30 hover:text-primary"
          >
            <ArrowLeft size={14} />
            Workspace
          </Link>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
