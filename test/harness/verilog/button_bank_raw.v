module \iceboy::periph::button_bank::button_bank_raw[2874] #(
    parameter integer N = 8,
    parameter integer DEBOUNCE_BITS = 8,
    parameter integer O = N * 4
) (
    input  wire              CLK_i,
    input  wire [N-1:0]      BUTTONS_I_i,
    output wire [O-1:0]      output__
);
    reg [N-1:0] sync_stage0 = {N{1'b0}};
    reg [N-1:0] sync_stage1 = {N{1'b0}};
    reg [N-1:0] debounced_reg = {N{1'b0}};
    reg [N-1:0] rising_reg = {N{1'b0}};
    reg [N-1:0] falling_reg = {N{1'b0}};
    reg [DEBOUNCE_BITS-1:0] counters [0:N-1];

    integer i;
    reg [DEBOUNCE_BITS-1:0] next_counter;
    reg next_debounced;

    assign output__ = {falling_reg, rising_reg, debounced_reg, sync_stage1};

    initial begin
        for (i = 0; i < N; i = i + 1) begin
            counters[i] = {DEBOUNCE_BITS{1'b0}};
        end
    end

    always @(posedge CLK_i) begin
        sync_stage0 <= BUTTONS_I_i;
        sync_stage1 <= sync_stage0;

        for (i = 0; i < N; i = i + 1) begin
            if (sync_stage1[i]) begin
                if (counters[i] == {DEBOUNCE_BITS{1'b1}}) begin
                    next_counter = counters[i];
                end else begin
                    next_counter = counters[i] + {{(DEBOUNCE_BITS - 1){1'b0}}, 1'b1};
                end
            end else begin
                if (counters[i] == {DEBOUNCE_BITS{1'b0}}) begin
                    next_counter = counters[i];
                end else begin
                    next_counter = counters[i] - {{(DEBOUNCE_BITS - 1){1'b0}}, 1'b1};
                end
            end

            next_debounced = next_counter[DEBOUNCE_BITS - 1];
            rising_reg[i] <= next_debounced && !debounced_reg[i];
            falling_reg[i] <= !next_debounced && debounced_reg[i];
            counters[i] <= next_counter;
            debounced_reg[i] <= next_debounced;
        end
    end
endmodule
