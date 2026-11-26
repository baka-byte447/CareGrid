import { useId, useState, type FormEvent } from 'react';
import { getErrorMessage, useCreateBed } from '@/api/hooks';
import { BedCreateRequestSchema } from '@/api/schemas';
import { ApiRequestError } from '@/api/client';
import { useToast } from '@/components/feedback/Toast';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Input, Select } from '@/components/ui/Input';
import { WARD_TYPE_LABELS, WARD_TYPE_LIST } from '@/lib/constants';

export function AddBedDialog({ wards, onClose }: { wards: string[]; onClose: () => void }) {
  const formId = useId();
  const { showToast } = useToast();
  const createBed = useCreateBed();
  const { error, isPending } = createBed;
  const [validationError, setValidationError] = useState<string | null>(null);
  const errorMessage = validationError ?? (
    error instanceof ApiRequestError && error.status === 422
      ? 'Check the bed details and try again.'
      : error && getErrorMessage(error)
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isPending) return;

    const form = new FormData(event.currentTarget);
    const request = BedCreateRequestSchema.safeParse({
      bed_id: form.get('bed_id'),
      bed_type: form.get('bed_type'),
      ward: form.get('ward'),
      isolation_capable: form.has('isolation_capable'),
    });

    if (!request.success) {
      setValidationError('Enter a valid bed ID, bed type, and ward.');
      return;
    }

    setValidationError(null);
    createBed.mutate(request.data, {
      onSuccess: (bed) => {
        showToast({ type: 'success', title: 'Bed added', message: `Bed ${bed.bed_id} is available in ${bed.ward}.` });
        onClose();
      },
    });
  }

  return (
    <Dialog
      isOpen
      onClose={() => { if (!isPending) onClose(); }}
      title="Add Bed"
      description="New beds are registered as available."
      maxWidth="sm"
      footer={
        <>
          <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button type="submit" form={formId} size="sm" isLoading={isPending}>
            Add Bed
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={handleSubmit}>
        <fieldset disabled={isPending} className="space-y-4">
          <label className="block space-y-1.5 text-sm font-medium">
            <span>Bed ID</span>
            <Input name="bed_id" required maxLength={10} pattern=".*\S.*" autoFocus />
          </label>
          <label className="block space-y-1.5 text-sm font-medium">
            <span>Bed Type</span>
            <Select name="bed_type" required defaultValue="" className="w-full">
              <option value="" disabled>Select a bed type</option>
              {WARD_TYPE_LIST.map((type) => (
                <option key={type} value={type}>{WARD_TYPE_LABELS[type]}</option>
              ))}
            </Select>
          </label>
          <label className="block space-y-1.5 text-sm font-medium">
            <span>Ward</span>
            <Input name="ward" required maxLength={50} pattern=".*\S.*" list={formId + '-wards'} />
          </label>
          <datalist id={formId + '-wards'}>
            {wards.map((ward) => <option key={ward} value={ward} />)}
          </datalist>
          <label className="flex items-center gap-2 text-sm font-medium">
            <input name="isolation_capable" type="checkbox" className="accent-brand-primary" />
            Isolation capable
          </label>
        </fieldset>
        {errorMessage && (
          <p role="alert" className="mt-4 text-sm text-rose-700 dark:text-rose-300">
            {errorMessage}
          </p>
        )}
      </form>
    </Dialog>
  );
}
