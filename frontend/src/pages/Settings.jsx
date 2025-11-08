import React, { useEffect, useState } from 'react';
import {
  Box,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Input,
  Textarea,
  HStack,
  useToast,
} from '@chakra-ui/react';
import axios from 'axios';

const Settings = () => {
  const [blacklist, setBlacklist] = useState([]);
  const [filename, setFilename] = useState('');
  const [reason, setReason] = useState('');
  const toast = useToast();

  const loadBlacklist = async () => {
    try {
      const resp = await axios.get('/api/blacklist');
      setBlacklist(resp.data || []);
    } catch (err) {
      console.error('Failed to load blacklist', err);
      toast({ title: 'Failed to load blacklist', status: 'error' });
    }
  };

  useEffect(() => {
    loadBlacklist();
  }, []);

  const handleAdd = async () => {
    if (!filename) return;
    try {
      const resp = await axios.post('/api/blacklist', { filename, reason });
      toast({ title: 'Blacklisted', description: `Added ${resp.data.filename}` });
      setFilename('');
      setReason('');
      loadBlacklist();
    } catch (err) {
      console.error('Add blacklist failed', err);
      toast({ title: 'Failed to add blacklist', status: 'error' });
    }
  };

  const handleRemove = async (id) => {
    try {
      await axios.delete(`/api/blacklist/${id}`);
      toast({ title: 'Un-blacklisted' });
      loadBlacklist();
    } catch (err) {
      console.error('Remove failed', err);
      toast({ title: 'Failed to remove', status: 'error' });
    }
  };

  return (
    <Box>
      <Heading size="md" mb={4}>Settings</Heading>

      <Box mb={6} p={4} bg="white" borderRadius="md" shadow="sm">
        <Heading size="sm" mb={3}>Manage Blacklist</Heading>
        <HStack spacing={3} mb={3}>
          <Input placeholder="Filename to blacklist (exact match)" value={filename} onChange={(e) => setFilename(e.target.value)} />
          <Button onClick={handleAdd} colorScheme="red">Add</Button>
        </HStack>
        <Textarea placeholder="Optional reason" value={reason} onChange={(e) => setReason(e.target.value)} mb={3} />
      </Box>

      <Box p={4} bg="white" borderRadius="md" shadow="sm">
        <Heading size="sm" mb={3}>Blacklisted documents</Heading>
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Filename</Th>
              <Th>Reason</Th>
              <Th>Blacklisted At</Th>
              <Th>Actions</Th>
            </Tr>
          </Thead>
          <Tbody>
            {blacklist.map((d) => (
              <Tr key={d.id}>
                <Td>{d.filename}</Td>
                <Td>{d.blacklist_reason}</Td>
                <Td>{d.blacklisted_at ? new Date(d.blacklisted_at).toLocaleString() : ''}</Td>
                <Td>
                  <Button size="sm" onClick={() => handleRemove(d.id)}>Unblacklist</Button>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
    </Box>
  );
};

export default Settings;
