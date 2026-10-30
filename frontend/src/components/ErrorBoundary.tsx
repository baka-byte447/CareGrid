import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertOctagon, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('CareGrid Uncaught UI Error:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-screen flex flex-col items-center justify-center p-6 bg-bg-page text-text-primary text-center">
          <div className="p-4 rounded-full bg-red-500/10 text-red-600 dark:text-red-400 mb-4">
            <AlertOctagon className="w-12 h-12" />
          </div>
          <h1 className="text-xl font-bold mb-2">Hospital Interface Interrupted</h1>
          <p className="text-xs text-text-muted max-w-md mb-6 leading-relaxed">
            An unexpected error occurred rendering the clinical interface. Diagnostic information has been logged.
          </p>
          <div className="p-4 mb-6 bg-bg-surface border border-border-light rounded-lg text-left max-w-lg w-full font-mono text-xs text-red-600 dark:text-red-400 overflow-x-auto">
            {this.state.error?.message || 'Unknown runtime error'}
          </div>
          <Button
            onClick={this.handleReset}
            variant="primary"
            leftIcon={<RotateCcw className="w-4 h-4" />}
          >
            Reload Interface
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
