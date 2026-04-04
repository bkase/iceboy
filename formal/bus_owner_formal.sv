`default_nettype none

module bus_owner_formal;
    localparam [1:0] OWNER_CPU = 2'd0;
    localparam [1:0] OWNER_OAM_DMA = 2'd1;
    localparam [1:0] OWNER_PPU = 2'd2;
    localparam [1:0] OWNER_IDLE = 2'd3;

    wire clk = $global_clock;

    reg rst = 1'b1;
    reg past_valid = 1'b0;

    (* anyseq *) reg m_ce;
    (* anyseq *) reg [1:0] req_kind;
    (* anyseq *) reg [15:0] addr;
    (* anyseq *) reg [7:0] data;
    (* anyseq *) reg oam_dma_active;
    (* anyseq *) reg ppu_vram_active;
    (* anyseq *) reg ppu_oam_active;

    wire [6:0] packed_output;
    wire [3:0] region = packed_output[6:3];
    wire [1:0] owner = packed_output[2:1];
    wire blocked = packed_output[0];
    wire req_active = req_kind == 2'd1 || req_kind == 2'd2;

    \iceboy::bus::observe_req_test_top::observe_req_test_top dut (
        .rst_i(rst),
        .m_ce_i(m_ce),
        .req_kind_i(req_kind),
        .addr_i(addr),
        .data_i(data),
        .oam_dma_active_i(oam_dma_active),
        .ppu_vram_active_i(ppu_vram_active),
        .ppu_oam_active_i(ppu_oam_active),
        .output__(packed_output)
    );

    always @(posedge clk) begin
        past_valid <= 1'b1;
        rst <= 1'b0;
    end

    always @(*) begin
        assert(owner == OWNER_CPU || owner == OWNER_OAM_DMA || owner == OWNER_PPU || owner == OWNER_IDLE);

        if (owner == OWNER_IDLE) begin
            assert(rst || !m_ce || !req_active);
        end

        if (!rst && m_ce && req_active && oam_dma_active && (addr < 16'hFF00 || addr == 16'hFFFF)) begin
            assert(owner == OWNER_OAM_DMA);
            assert(blocked);
        end

        if (!rst && m_ce && req_active && oam_dma_active && addr >= 16'hFF00 && addr <= 16'hFFFE) begin
            assert(owner == OWNER_CPU);
            assert(!blocked);
        end

        if (!rst && m_ce && req_active && !oam_dma_active && ppu_vram_active && addr >= 16'h8000 && addr <= 16'h9FFF) begin
            assert(owner == OWNER_PPU);
            assert(blocked);
        end

        if (!rst && m_ce && req_active && !oam_dma_active && ppu_oam_active && addr >= 16'hFE00 && addr <= 16'hFE9F) begin
            assert(owner == OWNER_PPU);
            assert(blocked);
        end

    end

    always @(posedge clk) begin
        if (past_valid
            && rst == $past(rst)
            && m_ce == $past(m_ce)
            && req_kind == $past(req_kind)
            && addr == $past(addr)
            && data == $past(data)
            && oam_dma_active == $past(oam_dma_active)
            && ppu_vram_active == $past(ppu_vram_active)
            && ppu_oam_active == $past(ppu_oam_active)) begin
            assert(owner == $past(owner));
            assert(blocked == $past(blocked));
            assert(region == $past(region));
        end
    end
endmodule

`default_nettype wire
