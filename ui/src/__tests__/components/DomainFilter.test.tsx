import { render, screen, fireEvent } from '@testing-library/react';
import { DomainFilter } from '@/components/DomainFilter';
import { Domain } from '@/types/industroml';

describe('DomainFilter', () => {
  const mockDomainCounts = {
    electrical: 5,
    mechanical: 3,
    data: 2,
    control: 1,
    safety: 0
  };

  const mockOnDomainChange = jest.fn();

  beforeEach(() => {
    mockOnDomainChange.mockClear();
  });

  it('should render all domain buttons', () => {
    render(
      <DomainFilter
        selectedDomain={undefined}
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    expect(screen.getByText('All Domains')).toBeInTheDocument();
    expect(screen.getByText('electrical')).toBeInTheDocument();
    expect(screen.getByText('mechanical')).toBeInTheDocument();
    expect(screen.getByText('data')).toBeInTheDocument();
    expect(screen.getByText('control')).toBeInTheDocument();
    expect(screen.getByText('safety')).toBeInTheDocument();
  });

  it('should display correct counts for each domain', () => {
    render(
      <DomainFilter
        selectedDomain={undefined}
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    expect(screen.getByText('5')).toBeInTheDocument(); // electrical
    expect(screen.getByText('3')).toBeInTheDocument(); // mechanical
    expect(screen.getByText('2')).toBeInTheDocument(); // data
    expect(screen.getByText('1')).toBeInTheDocument(); // control
    expect(screen.getByText('0')).toBeInTheDocument(); // safety
  });

  it('should show total count on All Domains button', () => {
    render(
      <DomainFilter
        selectedDomain={undefined}
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    expect(screen.getByText('11')).toBeInTheDocument(); // 5+3+2+1+0
  });

  it('should highlight selected domain', () => {
    render(
      <DomainFilter
        selectedDomain="electrical"
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    const buttons = screen.getAllByRole('button');
    const electricalButton = buttons.find(button => button.textContent?.includes('electrical'));
    expect(electricalButton).toBeDefined();
    expect(electricalButton).toHaveStyle({ backgroundColor: '#dc2626' });
  });

  it('should call onDomainChange when domain button is clicked', () => {
    render(
      <DomainFilter
        selectedDomain={undefined}
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    const buttons = screen.getAllByRole('button');
    const electricalButton = buttons.find(button => button.textContent?.includes('electrical'));
    expect(electricalButton).toBeDefined();
    
    fireEvent.click(electricalButton!);
    expect(mockOnDomainChange).toHaveBeenCalledWith('electrical');
  });

  it('should deselect domain when selected domain is clicked again', () => {
    render(
      <DomainFilter
        selectedDomain="electrical"
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    const buttons = screen.getAllByRole('button');
    const electricalButton = buttons.find(button => button.textContent?.includes('electrical'));
    expect(electricalButton).toBeDefined();
    
    fireEvent.click(electricalButton!);
    expect(mockOnDomainChange).toHaveBeenCalledWith(undefined);
  });

  it('should disable domains with zero count', () => {
    render(
      <DomainFilter
        selectedDomain={undefined}
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    // Find the safety button by looking for the button with "safety" text
    const buttons = screen.getAllByRole('button');
    const safetyButton = buttons.find(button => button.textContent?.includes('safety'));
    expect(safetyButton).toBeDefined();
    expect(safetyButton).toBeDisabled();
  });

  it('should call onDomainChange with undefined when All Domains is clicked', () => {
    render(
      <DomainFilter
        selectedDomain="electrical"
        onDomainChange={mockOnDomainChange}
        domainCounts={mockDomainCounts}
      />
    );

    const buttons = screen.getAllByRole('button');
    const allDomainsButton = buttons.find(button => button.textContent?.includes('All Domains'));
    expect(allDomainsButton).toBeDefined();
    
    fireEvent.click(allDomainsButton!);
    expect(mockOnDomainChange).toHaveBeenCalledWith(undefined);
  });
});