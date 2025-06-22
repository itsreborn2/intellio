'use client'

import { useEffect, useState, useCallback } from 'react'
import { IUser } from '@/types'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from 'intellio-common/components/ui/table'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from 'intellio-common/components/ui/pagination'
import { Badge } from 'intellio-common/components/ui/badge'
import { Input } from 'intellio-common/components/ui/input'
import { Button } from 'intellio-common/components/ui/button'

interface UserListResponse {
  total: number;
  users: IUser[];
}

async function fetchUsers(
  page: number,
  limit: number,
  email?: string
): Promise<UserListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });
  if (email) {
    params.append('email', email);
  }

  try {
    const response = await fetch(`/api/v1/dashboard/users?${params.toString()}`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to fetch users');
    }

    return await response.json();
  } catch (error) {
    console.error('Error fetching users:', error);
    return { total: 0, users: [] };
  }
}

export default function UserTable() {
  const [users, setUsers] = useState<IUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [inputValue, setInputValue] = useState(''); // State for the input field
  const [searchTerm, setSearchTerm] = useState(''); // State for the actual search query
  const [totalUsers, setTotalUsers] = useState(0);

  const limit = 20;

  const loadUsers = useCallback(async (page: number, email?: string) => {
    setLoading(true);
    setError(null);
    try {
      const { total, users: fetchedUsers } = await fetchUsers(
        page,
        limit,
        email
      );
      setUsers(fetchedUsers);
      setTotalUsers(total);
      setTotalPages(Math.ceil(total / limit));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  // useEffect now depends on the applied searchTerm, not the live input value
  useEffect(() => {
    loadUsers(currentPage, searchTerm);
  }, [currentPage, searchTerm, loadUsers]);

  // handleSearch applies the input value to the searchTerm state
  const handleSearch = () => {
    setCurrentPage(1); // Reset to first page on new search
    setSearchTerm(inputValue);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setCurrentPage(newPage);
    }
  };

  if (error) {
    return <div>Error: {error}</div>;
  }

  return (
    <div>
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter by email..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="max-w-sm rounded-[6px]"
        />
        <Button onClick={handleSearch} className="ml-2 rounded-[6px]">Search</Button>
      </div>
      <div className="rounded-[6px] border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>OAuth Provider</TableHead>
              <TableHead>Profile Image</TableHead>
              <TableHead>Registered At</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.name}</TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? 'default' : 'destructive'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.is_superuser ? 'secondary' : 'outline'}>
                      {user.is_superuser ? 'Admin' : 'User'}
                    </Badge>
                  </TableCell>
                  <TableCell>{user.oauth_provider || 'N/A'}</TableCell>
                  <TableCell>
                    {user.profile_image ? (
                      <img
                        src={user.profile_image}
                        alt={user.name}
                        className="h-10 w-10 rounded-full object-cover"
                      />
                    ) : (
                      'N/A'
                    )}
                  </TableCell>
                  <TableCell>
                    {user.created_at
                      ? new Date(user.created_at).toLocaleDateString()
                      : 'N/A'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious href="#" onClick={() => handlePageChange(currentPage - 1)} />
            </PaginationItem>
            {[...Array(totalPages)].map((_, i) => (
              <PaginationItem key={i}>
                <PaginationLink href="#" isActive={currentPage === i + 1} onClick={() => handlePageChange(i + 1)}>
                  {i + 1}
                </PaginationLink>
              </PaginationItem>
            ))}
            <PaginationItem>
              <PaginationNext href="#" onClick={() => handlePageChange(currentPage + 1)} />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  );
}
