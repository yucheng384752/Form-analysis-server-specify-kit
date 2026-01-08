import React, { useState, useEffect } from 'react';
import { Modal } from './common/Modal';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

interface EditReason {
  id: string;
  reason_code: string;
  description: string;
}

interface EditRecordModalProps {
  open: boolean;
  record: any;
  type: 'P1' | 'P2' | 'P3';
  onClose: () => void;
  onSave: (updatedRecord: any) => void;
  tenantId: string; // We need tenant ID
}

export const EditRecordModal: React.FC<EditRecordModalProps> = ({
  open,
  record,
  type,
  onClose,
  onSave,
  tenantId
}) => {
  const [reasons, setReasons] = useState<EditReason[]>([]);
  const [selectedReason, setSelectedReason] = useState<string>('');
  const [customReason, setCustomReason] = useState('');
  const [formData, setFormData] = useState<any>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && record) {
      // Initialize form data with editable fields
      // For P1: quantity, product_name, production_date
      // For others: TBD
      const initialData: any = {};
      if (type === 'P1') {
        initialData.quantity = record.quantity;
        initialData.product_name = record.product_name;
        initialData.production_date = record.production_date;
      }
      // Add more fields as needed
      setFormData(initialData);
      
      // Fetch reasons
      fetchReasons();
    }
  }, [open, record, type]);

  const fetchReasons = async () => {
    try {
      const res = await fetch(`/api/edit/reasons?tenant_id=${tenantId}`);
      if (res.ok) {
        const data = await res.json();
        setReasons(data);
      }
    } catch (error) {
      console.error("Failed to fetch reasons", error);
    }
  };

  const handleSave = async () => {
    if (!selectedReason) {
      alert("Please select a reason");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        tenant_id: tenantId,
        updates: formData,
        reason_id: selectedReason,
        reason_text: customReason
      };

      const res = await fetch(`/api/edit/records/${type}/${record.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const updated = await res.json();
        onSave(updated);
        onClose();
      } else {
        const err = await res.json();
        alert(`Update failed: ${err.detail}`);
      }
    } catch (error) {
      console.error("Update error", error);
      alert("Update failed");
    } finally {
      setLoading(false);
    }
  };

  if (!record) return null;

  return (
    <Modal open={open} onClose={onClose} title={`Edit ${type} Record`}>
      <div className="space-y-4 p-4">
        {/* Fields */}
        {Object.keys(formData).map(key => (
          <div key={key} className="grid grid-cols-4 items-center gap-4">
            <Label className="text-right">{key}</Label>
            <Input 
              className="col-span-3"
              value={formData[key] || ''}
              onChange={e => setFormData({...formData, [key]: e.target.value})}
            />
          </div>
        ))}

        {/* Reason */}
        <div className="grid grid-cols-4 items-center gap-4 border-t pt-4">
          <Label className="text-right">Reason</Label>
          <div className="col-span-3">
            <Select value={selectedReason} onValueChange={setSelectedReason}>
              <SelectTrigger>
                <SelectValue placeholder="Select reason" />
              </SelectTrigger>
              <SelectContent>
                {reasons.map(r => (
                  <SelectItem key={r.id} value={r.id}>{r.description}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {selectedReason && reasons.find(r => r.id === selectedReason)?.reason_code === 'OTHER' && (
           <div className="grid grid-cols-4 items-center gap-4">
             <Label className="text-right">Note</Label>
             <Input 
               className="col-span-3"
               placeholder="Specify reason"
               value={customReason}
               onChange={e => setCustomReason(e.target.value)}
             />
           </div>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
