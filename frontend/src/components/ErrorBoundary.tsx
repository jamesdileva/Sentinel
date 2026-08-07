import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches render-time errors in descendant routes and shows a recoverable
 * fallback instead of a blank page (Sprint 12 polish).
 */
export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Sentinel route crashed:", error, info);
  }

  render(): ReactNode {
    if (this.state.error === null) return this.props.children;
    return (
      <section
        aria-label="Something went wrong"
        className="flex flex-col items-start gap-3 rounded-xl border border-red-300 bg-red-50 p-6 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
      >
        <h2 className="text-lg font-semibold text-red-900 dark:text-red-100">
          Something went wrong
        </h2>
        <p className="text-sm text-red-800 dark:text-red-200">
          {this.state.error.message}
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-50 dark:border-red-800 dark:bg-red-950 dark:text-red-200 dark:hover:bg-red-900"
        >
          Try again
        </button>
      </section>
    );
  }
}
