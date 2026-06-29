"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            role="alert"
            aria-live="assertive"
            className="flex flex-col items-center justify-center p-8 text-center"
          >
            <p className="text-lg font-semibold text-red-600">
              Etwas ist schiefgelaufen.
            </p>
            <p className="mt-2 text-sm text-gray-500">
              {this.state.error?.message}
            </p>
            <button
              className="mt-4 rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Erneut versuchen
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}